// The live-editing rules as a Hocuspocus extension (spec 9, plan M2 task 9).
//
// One WebSocket edits one page: the page id and the generation the browser's
// document belongs to come from the connection URL (`/collab/<page id>?generation=N`),
// and the document name must be `page:<that id>`. Every connection authenticates
// with the person's session cookie at the API (`/internal/collab/auth`).
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
// state together with the sessions that edited since the last save. Every 5 s each
// open document asks the API whether its generation and its people still hold.
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
import { randomUUID } from "node:crypto";
import * as Y from "yjs";
import { ApiUnavailable } from "./api.mjs";
import { documentRules } from "./documents.mjs";
import { inlineChecks } from "./checks.mjs";
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
  readCookie,
} from "./protocol.mjs";

export { CLOSE, colorFor, readCookie } from "./protocol.mjs";

const DENIAL = {
  401: CLOSE.unauthorized,
  403: CLOSE.forbidden,
  404: CLOSE.notFound,
  413: CLOSE.tooLarge,
};

/** `person(context, userId)`: false when the person holds too many connections.
 * `checks`: where the heavy checks run (`checks.mjs`). */
export function liveExtension({
  api,
  cookieName,
  retryMs = 5000,
  log = () => {},
  person = () => true,
  checks = inlineChecks(),
  ...limits
}) {
  const size = sizeGuard(limits);
  const presence = presenceGuard();
  const live = new Map(); // document name -> { pageId, generation, sessionKey, dirty, seen, ... }
  const joined = new WeakSet(); // sockets that completed the handshake and joined a document
  const ending = new Set(); // document names whose generation must end before anyone joins

  const { discard, checkDocument, store } = documentRules({ api, log, retryMs, ending, checks });

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

    async onAuthenticate({ documentName, requestHeaders, context }) {
      if (documentName !== `page:${context.pageId}`) throw deny(context, CLOSE.forbidden);
      if (ending.has(documentName)) throw deny(context, CLOSE.retry);
      const token = readCookie(requestHeaders.get("cookie"), cookieName);
      if (!token) throw deny(context, CLOSE.unauthorized);
      let answer;
      try {
        answer = await api.auth(token, context.pageId);
      } catch (error) {
        if (error instanceof ApiUnavailable) throw deny(context, CLOSE.retry);
        throw error;
      }
      if (answer.status !== 200) throw deny(context, DENIAL[answer.status] ?? CLOSE.forbidden);
      if (answer.body.generation !== context.generation) throw deny(context, CLOSE.generationEnded);
      if (!person(context, answer.body.user.id)) throw deny(context, CLOSE.tooMany);
      return { user: answer.body.user, sessionId: answer.body.session_id };
    },

    async onLoadDocument({ document, documentName, context }) {
      const answer = await api.load(context.pageId, context.sessionId, context.generation);
      if (answer.status === 409) throw deny(context, CLOSE.generationEnded);
      if (answer.status !== 200) throw deny(context, DENIAL[answer.status] ?? CLOSE.forbidden);
      const { generation, ydoc_b64: stored, content_md: contentMd } = answer.body;
      const state = { pageId: context.pageId, generation, sessionKey: randomUUID() };
      Object.assign(state, { dirty: new Map(), seen: new Set(), discarded: false, holding: false });
      // The heavy work runs on a check worker (`checks.mjs`, review M2 T9).
      let opened;
      if (stored) {
        // A state the browser's editor would repair (and save repaired) is not opened;
        // one it would only tidy without changing its meaning is tidied, so the browser
        // has nothing left to change (review M2 T1, ruling A).
        const bytes = Buffer.from(stored, "base64");
        opened = await checks.tidy(bytes);
        if (opened.problem !== null) throw deny(context, CLOSE.notRoundTripSafe);
        Y.applyUpdate(document, bytes);
      } else {
        // Only a page the editor can show without changing its meaning is opened, as the
        // browser's editor shows it once loaded.
        opened = await checks.open(contentMd);
        if (!opened.safe) throw deny(context, CLOSE.notRoundTripSafe);
      }
      const tidied = opened.update !== null;
      if (tidied) Y.applyUpdate(document, opened.update);
      if (tidied) {
        // Built or tidied here: saved at once (content unchanged, so no version), so a
        // browser that reconnects later meets the same Yjs history.
        const saved = await api.save(context.pageId, {
          generation,
          ydoc: Y.encodeStateAsUpdate(document),
          contentMd,
          editorSessionIds: [context.sessionId],
          sessionKey: state.sessionKey,
        });
        if (saved.status === 409) throw deny(context, CLOSE.generationEnded);
        if (saved.status !== 200) throw deny(context, DENIAL[saved.status] ?? CLOSE.forbidden);
      }
      state.source = contentMd;
      state.baseline = opened.baseline;
      state.size = size.measure(document);
      live.set(documentName, state);
    },

    async connected({ connection, documentName, context, instance }) {
      const state = live.get(documentName);
      if (!state || state.discarded || state.holding) return closeSocket(context, CLOSE.retry);
      state.seen.add(context.sessionId);
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
      if (!state || state.discarded || state.holding || !state.dirty.has(context?.sessionId)) {
        return;
      }
      instance.storeDocumentHooks(document, { document, documentName, instance }, true);
    },

    async onChange({ connection, context, documentName }) {
      const state = live.get(documentName);
      if (connection && state && context?.sessionId) state.dirty.set(context.sessionId, true);
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
