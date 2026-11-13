// The live-editing rules as a Hocuspocus extension (spec 9, plan M2 task 9).
//
// One WebSocket edits one page: the page id and the generation the browser's
// document belongs to come from the connection URL (`/collab/<page id>?generation=N`),
// and the document name must be `page:<that id>`. Every connection authenticates
// with the person's session cookie at the API (`/internal/collab/auth`).
//
// A page is opened only if the editor can show it without changing what it means
// (`liveDocument` in markdown.mjs); otherwise 4422 `collab.not_roundtrip_safe`. A save
// whose Markdown equals what was loaded keeps the stored Markdown as it was written.
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
import { jsonToYDoc, liveDocument, yDocToMarkdown } from "./markdown.mjs";

export const CLOSE = {
  generationEnded: [4409, "generation_ended"],
  revoked: [4403, "revoked"],
  forbidden: [4403, "forbidden"],
  unauthorized: [4401, "unauthorized"],
  notFound: [4404, "not_found"],
  tooLarge: [4413, "too_large"],
  notRoundTripSafe: [4422, "collab.not_roundtrip_safe"],
  retry: [1013, "retry"],
};

// Stateless messages: a browser that is done asks for an immediate save (`flush`) and
// is told whether everything it sent is stored (review M2 R3).
export const FLUSH = "herd:flush";
export const SAVED = "herd:saved";
export const UNSAVED = "herd:unsaved";
const FLUSH_INTERVAL_MS = 1000; // at most one forced save per connection per second

const DENIAL = { 401: CLOSE.unauthorized, 403: CLOSE.forbidden, 404: CLOSE.notFound };
// Tailwind's 700 shades: white text on each has at least 4.5:1 (WCAG AA), and the
// browser shows initials in white on them.
const COLORS = ["#1d4ed8", "#be185d", "#15803d", "#b45309", "#6d28d9", "#0e7490", "#b91c1c"];

export function colorFor(id) {
  let hash = 0;
  for (const char of String(id)) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

/** Close the connection's socket (after the protocol message just sent). */
function closeSocket(context, close) {
  context.closing ??= close; // the first reason stands
  setTimeout(() => context.socket?.close(...context.closing), 0);
}

function deny(context, close) {
  closeSocket(context, close);
  return Object.assign(new Error(close[1]), { reason: close[1] });
}

export function liveExtension({ api, cookieName, retryMs = 5000, log = () => {} }) {
  const live = new Map(); // document name -> { pageId, generation, sessionKey, dirty, seen, ... }
  const ending = new Set(); // document names whose generation must end before anyone joins

  function discard(document, state, close) {
    state.discarded = true;
    for (const connection of document.getConnections()) closeSocket(connection.context, close);
    log("live document dropped", { page_id: state.pageId, reason: close[1] });
  }

  function revoke(document, sessionIds, userIds) {
    for (const connection of document.getConnections()) {
      const { context } = connection;
      if (sessionIds.has(context.sessionId) || userIds.has(context.user?.id)) {
        closeSocket(context, CLOSE.revoked);
      }
    }
  }

  /** Ask the API whether the generation and the people still hold; true when the
   * document was dropped. The unsaved sessions go along: one of them revoked ends the
   * generation. Throws `ApiUnavailable`. */
  async function checkDocument(document, documentName, state) {
    const connected = document.getConnections().map((c) => c.context.sessionId);
    // Sessions that left are checked too (the API takes the organisation from the page).
    const sessionIds = [...new Set([...connected, ...state.seen].filter(Boolean))].slice(0, 200);
    const unsaved = [...state.dirty.keys()];
    if (sessionIds.length === 0 && unsaved.length === 0) return false;
    const answer = await api.check(state.pageId, sessionIds, state.generation, unsaved);
    if (answer.status !== 200) return false;
    const { revoked_session_ids: sessions, revoked_user_ids: users } = answer.body;
    revoke(document, new Set(sessions), new Set(users));
    if (!answer.body.generation_ok) {
      discard(document, state, CLOSE.generationEnded);
      return true;
    }
    const ended = new Set(answer.body.ended_session_ids ?? []);
    if (ended.size > 0) await endSessions(document, documentName, state, ended);
    return false;
  }

  /** Sessions that ended (logout, expiry) of people who may still edit: their edits
   * are saved first, then their connections close with 4401. */
  async function endSessions(document, documentName, state, ended) {
    const unsaved = [...ended].some((sessionId) => state.dirty.has(sessionId));
    if (unsaved && !state.holding && !state.discarded) {
      try {
        await document.saveMutex.runExclusive(() => store(document, documentName, state));
      } catch (error) {
        if (!(error instanceof ApiUnavailable)) throw error; // still dirty: saved later
      }
    }
    for (const connection of document.getConnections()) {
      if (ended.has(connection.context.sessionId)) {
        closeSocket(connection.context, CLOSE.unauthorized);
      }
    }
  }

  /** A save was refused for revoked editors: hold the document until the API has
   * ended the generation (or the rights are back), retrying while it is away. */
  async function endGeneration(document, documentName, state) {
    state.holding = true;
    ending.add(documentName);
    try {
      await checkDocument(document, documentName, state);
    } catch (error) {
      if (!(error instanceof ApiUnavailable)) throw error;
      log("live check failed, retrying", { page_id: state.pageId });
      setTimeout(() => endGeneration(document, documentName, state), retryMs).unref();
      return;
    }
    ending.delete(documentName);
    state.holding = false;
  }

  async function store(document, documentName, state) {
    const editors = [...state.dirty.keys()];
    if (editors.length === 0) return;
    const ydoc = Y.encodeStateAsUpdate(document);
    let contentMd = yDocToMarkdown(document);
    // Unchanged from what was loaded (an edit undone, or a browser tidying the
    // document's structure): the stored Markdown stays exactly as it was written.
    if (contentMd === state.baseline) contentMd = state.source;
    for (const sessionId of editors) state.dirty.delete(sessionId);
    let answer;
    try {
      answer = await api.save(state.pageId, {
        generation: state.generation,
        ydoc,
        contentMd,
        editorSessionIds: editors,
        sessionKey: state.sessionKey,
      });
    } catch (error) {
      for (const sessionId of editors) state.dirty.set(sessionId, true);
      throw error;
    }
    if (answer.status === 200) return;
    if (answer.status === 409) return discard(document, state, CLOSE.generationEnded);
    if (answer.status === 403) {
      for (const sessionId of editors) state.dirty.set(sessionId, true); // still unsaved
      return endGeneration(document, documentName, state);
    }
    if (answer.status === 413) return discard(document, state, CLOSE.tooLarge);
    return discard(document, state, CLOSE.notFound);
  }

  return {
    extensionName: "herd-live",
    live,

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
      return { user: answer.body.user, sessionId: answer.body.session_id };
    },

    async onLoadDocument({ document, documentName, context }) {
      const answer = await api.load(context.pageId, context.sessionId, context.generation);
      if (answer.status === 409) throw deny(context, CLOSE.generationEnded);
      if (answer.status !== 200) throw deny(context, DENIAL[answer.status] ?? CLOSE.forbidden);
      const { generation, ydoc_b64: stored, content_md: contentMd } = answer.body;
      const state = { pageId: context.pageId, generation, sessionKey: randomUUID() };
      Object.assign(state, { dirty: new Map(), seen: new Set(), discarded: false, holding: false });
      if (stored) {
        Y.applyUpdate(document, Buffer.from(stored, "base64"));
      } else {
        // Only a page the editor can show without changing its meaning is opened.
        const converted = liveDocument(contentMd);
        if (!converted.safe) throw deny(context, CLOSE.notRoundTripSafe);
        // Built from the Markdown: saved at once (content unchanged, so no version),
        // so a browser that reconnects later meets the same Yjs history.
        Y.applyUpdate(document, Y.encodeStateAsUpdate(jsonToYDoc(converted.json)));
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
      state.baseline = yDocToMarkdown(document);
      live.set(documentName, state);
    },

    async connected({ documentName, context, instance }) {
      const state = live.get(documentName);
      if (!state || state.discarded || state.holding) return closeSocket(context, CLOSE.retry);
      state.seen.add(context.sessionId);
      if (context.generation < state.generation) return closeSocket(context, CLOSE.generationEnded);
      if (context.generation > state.generation) {
        // A newer generation is about: the document in memory is outdated.
        const document = instance.documents.get(documentName);
        if (document) discard(document, state, CLOSE.generationEnded);
        return closeSocket(context, CLOSE.retry);
      }
    },

    async beforeHandleMessage({ context, documentName }) {
      const state = live.get(documentName);
      let close = null;
      if (context.closing) close = context.closing;
      else if (!state || state.discarded) close = CLOSE.generationEnded;
      else if (state.holding) close = CLOSE.retry; // the generation is being ended
      if (close) throw Object.assign(new Error(close[1]), { code: close[0], reason: close[1] });
    },

    /** "I am done": save now, then say whether everything is stored. */
    async onStateless({ connection, document, documentName, payload }) {
      if (payload !== FLUSH) return;
      const state = live.get(documentName);
      const { context } = connection;
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
    async onDisconnect({ context, document, documentName, instance }) {
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

    async beforeHandleAwareness({ context, states }) {
      if (!context?.user) return;
      for (const awareness of states.values()) {
        awareness.user = { name: context.user.name, color: colorFor(context.user.id) };
      }
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

export function readCookie(header, name) {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return null;
}
