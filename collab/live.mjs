// The live-editing rules as a Hocuspocus extension (spec 9, plan M2 task 9).
//
// One WebSocket edits one page: the page id and the generation the browser's
// document belongs to come from the connection URL (`/collab/<page id>?generation=N`),
// and the document name must be `page:<that id>`. Every connection carries the grant
// the API's relay issued for exactly that page and generation (`server.mjs`; never the
// session cookie, plan M9 decision 16) and is admitted with it at the API
// (`/internal/collab/auth`); loads, saves and checks name the grants of the
// connections. The checks keep the grants alive.
//
// A page is opened only if the editor can show it without changing what it means
// (`liveDocument` in markdown.mjs); otherwise 4422 `collab.not_roundtrip_safe`. The
// document served is the one the browser's editor shows once it has loaded it (the
// collab process runs that editor headless, `settle.mjs`), so opening a page and
// leaving it sends nothing. A save
// stores only Markdown that reads back as the document (`documents.mjs`); one whose
// Markdown equals what was loaded keeps the stored Markdown as it was written.
//
// Saves (debounced 2 s, at the latest after 10 s) send the Markdown and the Yjs
// state together with the grants of the connections that edited since the last save.
// Every 5 s each open document asks the API whether its generation and its people
// still hold.
// - Generation ended (a change outside the live session): every connection is closed
//   with 4409 `generation_ended`, the document is dropped unsaved.
// - A person's login session ended (logout, expiry) while they may still edit: what
//   they typed is saved at once under their name, then their connections are closed
//   with 4401 `unauthorized`; everyone else goes on in the same generation. A
//   connection that leaves with unsaved edits is saved at once, too.
// - A person may no longer edit (right removed, deactivated, signed out by an
//   administrator or a password change): their connections are closed with 4403
//   `revoked`. If they edited since the last save,
//   the document holds edits no one may save, and every browser that saw them would
//   bring them back on reconnecting: the API ends the generation (the check names the
//   unsaved sessions), the document is dropped and everyone is closed with 4409. Until
//   the API has confirmed it, the document takes no messages and no one joins it.
import { ApiUnavailable } from "./api.mjs";
import { documentRules } from "./documents.mjs";
import { DENIAL, openRules } from "./opening.mjs";
import { inlineChecks } from "./checks.mjs";
import { memoryBudget } from "./memory.mjs";
import { presenceGuard } from "./presence.mjs";
import { sizeGuard } from "./size.mjs";
import {
  CLOSE,
  FLUSH,
  FLUSH_INTERVAL_MS,
  LOAD_MUTATION,
  SAVED,
  UNSAVED,
  closeSocket,
  deny,
} from "./protocol.mjs";

export { CLOSE, colorFor, readGrant } from "./protocol.mjs";

/** `person(context, {userId, sessionRef})`: false when the person or their login
 * session holds too many connections. `checks`: where the heavy checks run
 * (`checks.mjs`). */
export function liveExtension({
  api,
  retryMs = 5000,
  log = () => {},
  person = () => true,
  checks = inlineChecks(),
  memory = memoryBudget(),
  ...limits
}) {
  const size = sizeGuard(limits);
  const presence = presenceGuard();
  const live = new Map(); // document name -> { pageId, generation, sessionKey, dirty, seen, ... }
  const joined = new WeakSet(); // sockets that completed the handshake and joined a document
  const loading = new Set(); // document names being opened (waiting for or in a check)
  const ending = new Set(); // document names whose generation must end before anyone joins

  const { discard, checkDocument, store } = documentRules({ api, log, retryMs, ending, checks });
  const { load } = openRules({ api, log, checks, size, live, memory });

  /** A browser's editor changed the document it had just loaded and stopped (once per
   * connection: a browser cannot inflate the count). */
  async function loadMutation(context, state) {
    if (context.loadMutation || !state) return;
    context.loadMutation = true;
    log("live editor changed a loaded document", { page_id: state.pageId });
    try {
      await api.loadMutation(state.pageId);
    } catch (error) {
      if (!(error instanceof ApiUnavailable)) throw error; // only the count is missing
    }
  }

  return {
    extensionName: "herd-live",
    live,
    joined,
    loading,
    memory,

    async onAuthenticate({ documentName, context }) {
      if (documentName !== `page:${context.pageId}`) throw deny(context, CLOSE.forbidden);
      if (ending.has(documentName)) throw deny(context, CLOSE.retry);
      if (!context.grant) throw deny(context, CLOSE.unauthorized);
      let answer;
      try {
        answer = await api.auth(context.grant, context.pageId, context.generation);
      } catch (error) {
        if (error instanceof ApiUnavailable) throw deny(context, CLOSE.retry);
        throw error;
      }
      if (answer.status === 409) throw deny(context, CLOSE.generationEnded);
      if (answer.status !== 200) throw deny(context, DENIAL[answer.status] ?? CLOSE.forbidden);
      if (answer.body.generation !== context.generation) throw deny(context, CLOSE.generationEnded);
      const { user, session_ref: sessionRef } = answer.body;
      if (!person(context, { userId: user.id, sessionRef })) throw deny(context, CLOSE.tooMany);
      return { user };
    },

    async onLoadDocument({ document, documentName, context }) {
      loading.add(documentName);
      try {
        await load(document, documentName, context);
      } catch (error) {
        memory.release(documentName); // not loaded after all
        throw error;
      } finally {
        loading.delete(documentName);
      }
    },

    async connected({ connection, documentName, context, instance }) {
      const state = live.get(documentName);
      if (!state || state.discarded || state.holding) return closeSocket(context, CLOSE.retry);
      state.seen.add(context.grant);
      if (state.unrepresentable) connection.sendStateless(state.unrepresentable);
      if (context.generation < state.generation) return closeSocket(context, CLOSE.generationEnded);
      if (context.generation > state.generation) {
        // A newer generation is about: the document in memory is outdated.
        const document = instance.documents.get(documentName);
        if (document) discard(document, state, CLOSE.generationEnded);
        return closeSocket(context, CLOSE.retry);
      }
      joined.add(context.socket);
    },

    async beforeHandleMessage({ context, document, documentName, update }) {
      const refuse = (close) => {
        throw Object.assign(new Error(close[1]), { code: close[0], reason: close[1] });
      };
      const settled = () => {
        const state = live.get(documentName);
        if (context.closing) refuse(context.closing);
        if (!state || state.discarded) refuse(CLOSE.generationEnded);
        if (state.holding) refuse(CLOSE.retry); // the generation is being ended
        return state;
      };
      const admitted = await size.admit(document, settled(), update);
      settled(); // the measurement may have waited (T12): still as it was?
      if (!admitted) {
        closeSocket(context, CLOSE.tooLarge); // only this sender; the document stays as it was
        refuse(CLOSE.tooLarge);
      }
    },

    /** "I am done": save now, then say whether everything is stored. */
    async onStateless({ connection, document, documentName, payload }) {
      const state = live.get(documentName);
      const { context } = connection;
      if (payload === LOAD_MUTATION) return loadMutation(context, state);
      if (payload !== FLUSH) return;
      const now = Date.now();
      const due = now - (context.flushedAt ?? 0) >= FLUSH_INTERVAL_MS;
      if (state && due && state.dirty.size > 0 && !state.discarded && !state.holding) {
        context.flushedAt = now;
        try {
          await document.saveMutex.runExclusive(() => store(document, documentName, state));
        } catch (error) {
          if (!(error instanceof ApiUnavailable)) throw error;
        }
      }
      const stored = state && !state.discarded && state.dirty.size === 0;
      connection.sendStateless(stored ? SAVED : UNSAVED);
    },

    /** A connection that leaves with unsaved edits is saved at once, while its
     * session is surely still valid (logging out right after leaving loses nothing). */
    async onDisconnect({ context, document, documentName, instance, socketId }) {
      presence.forget(socketId);
      const state = live.get(documentName);
      if (!state || state.discarded || state.holding || !state.dirty.has(context?.grant)) {
        return;
      }
      instance.storeDocumentHooks(document, { document, documentName, instance }, true);
    },

    async onChange({ connection, context, documentName }) {
      const state = live.get(documentName);
      if (connection && state && context?.grant) state.dirty.set(context.grant, true);
    },

    async beforeHandleAwareness(payload) {
      presence.filter(payload);
    },

    async onStoreDocument({ document, documentName, instance }) {
      const state = live.get(documentName);
      if (!state || state.discarded || state.holding) return; // holding: nothing may be saved
      try {
        await store(document, documentName, state);
      } catch (error) {
        if (!(error instanceof ApiUnavailable)) throw error;
        log("live save failed, retrying", { page_id: state.pageId });
        setTimeout(() => {
          if (!state.discarded && instance.documents.get(documentName) === document) {
            instance.storeDocumentHooks(document, { document, documentName, instance });
          }
        }, retryMs).unref();
        throw error; // keeps the document in memory
      }
    },

    async afterUnloadDocument({ documentName }) {
      live.delete(documentName);
      memory.release(documentName);
    },

    /** Ask the API whether each open document's generation and people still hold. */
    async checkAll(instance) {
      for (const [documentName, document] of instance.documents) {
        const state = live.get(documentName);
        if (!state || state.discarded || state.holding) continue;
        try {
          await checkDocument(document, documentName, state);
        } catch (error) {
          if (!(error instanceof ApiUnavailable)) throw error;
        }
      }
    },
  };
}
