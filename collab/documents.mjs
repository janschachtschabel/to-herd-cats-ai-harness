// What happens to an open live document (`live.mjs`): saving it, checking whether its
// generation and its people still hold, ending sessions and generations.
//
// A save stores only Markdown that reads back as what the editors see and opens in
// the live editor again (`readback.mjs`, review M2 S2/S3). A state that cannot be
// written so is not stored: the last good Markdown stays, the API counts it
// (`herd_collab_saves_total{result="unrepresentable"}`), every connection is told
// (`herd:unrepresentable`, the session goes on) and the edits stay unsaved until a
// later state saves (`herd:representable`).
import * as Y from "yjs";
import { ApiUnavailable } from "./api.mjs";
import { yDocToJSON } from "./markdown.mjs";
import { CLOSE, REPRESENTABLE, UNREPRESENTABLE, closeSocket } from "./protocol.mjs";
import { readBack } from "./readback.mjs";

export function documentRules({ api, log, retryMs, ending }) {
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

  function tell(document, message) {
    for (const connection of document.getConnections()) connection.sendStateless(message);
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

  /** The latest state cannot be stored: say so (the edits stay unsaved). */
  async function unrepresentable(document, state, problem) {
    if (!state.unrepresentable) log("live save refused", { page_id: state.pageId, problem });
    state.unrepresentable = true;
    tell(document, UNREPRESENTABLE);
    try {
      await api.unrepresentable(state.pageId);
    } catch (error) {
      if (!(error instanceof ApiUnavailable)) throw error; // only the count is missing
    }
  }

  async function store(document, documentName, state) {
    const editors = [...state.dirty.keys()];
    if (editors.length === 0) return;
    const written = readBack(yDocToJSON(document));
    if (!written.ok) return unrepresentable(document, state, written.problem);
    const ydoc = Y.encodeStateAsUpdate(document);
    // Unchanged from what was loaded (an edit undone, or a browser tidying the
    // document's structure): the stored Markdown stays exactly as it was written.
    const contentMd = written.markdown === state.baseline ? state.source : written.markdown;
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
    if (answer.status === 200) {
      if (state.unrepresentable) tell(document, REPRESENTABLE);
      state.unrepresentable = false;
      return;
    }
    if (answer.status === 409) return discard(document, state, CLOSE.generationEnded);
    if (answer.status === 403) {
      for (const sessionId of editors) state.dirty.set(sessionId, true); // still unsaved
      return endGeneration(document, documentName, state);
    }
    if (answer.status === 413) return discard(document, state, CLOSE.tooLarge);
    if (answer.status === 404) return discard(document, state, CLOSE.notFound);
    return discard(document, state, CLOSE.saveRefused);
  }

  return { discard, checkDocument, store };
}
