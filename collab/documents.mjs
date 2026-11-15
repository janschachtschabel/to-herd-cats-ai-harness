// What happens to an open live document (`live.mjs`): saving it, checking whether its
// generation and its people still hold, ending sessions and generations.
//
// A save stores only Markdown that reads back as what the editors see and opens in
// the live editor again (`readback.mjs`, review M2 S2/S3). A state that cannot be
// written so is not stored: the last good Markdown stays, the API counts it
// (`herd_collab_saves_total{result="unrepresentable"}`), every connection is told
// (`herd:unrepresentable:<kind>:<where>`, the session goes on) and the edits stay unsaved until a
// later state saves (`herd:representable`). Every stored state is acknowledged to every
// connection with its snapshot (`herd:stored:`), so a browser knows when its own changes
// are stored.
import * as Y from "yjs";
import { ApiUnavailable } from "./api.mjs";
import { MAX_TABLE_CELLS, tableLoad } from "./cells.mjs";
import { CheckFailed, CheckTimedOut } from "./checks.mjs";
import { yDocToJSON } from "./markdown.mjs";
import { CLOSE, REPRESENTABLE, STORED, closeSocket, unrepresentableNotice } from "./protocol.mjs";

export function documentRules({ api, log, retryMs, ending, checks }) {
  function discard(document, state, close) {
    state.discarded = true;
    for (const connection of document.getConnections()) closeSocket(connection.context, close);
    log("live document dropped", { page_id: state.pageId, reason: close[1] });
  }

  function revoke(document, grants) {
    for (const connection of document.getConnections()) {
      const { context } = connection;
      if (grants.has(context.grant)) closeSocket(context, CLOSE.revoked);
    }
  }

  function tell(document, message) {
    for (const connection of document.getConnections()) connection.sendStateless(message);
  }

  /** Ask the API whether the generation and the people still hold; true when the
   * document was dropped. Every connection is known by its grant; the unsaved grants go
   * along: one of them revoked ends the generation. The check also keeps the grants
   * alive (they expire ten minutes after the last check). Throws `ApiUnavailable`. */
  async function checkDocument(document, documentName, state) {
    const connected = document.getConnections().map((c) => c.context.grant);
    // Grants of connections that left are checked too: their unsaved edits count.
    const grants = [...new Set([...connected, ...state.seen].filter(Boolean))].slice(0, 200);
    const unsaved = [...state.dirty.keys()];
    if (grants.length === 0 && unsaved.length === 0) return false;
    const answer = await api.check(state.pageId, grants, state.generation, unsaved);
    if (answer.status !== 200) return false;
    revoke(document, new Set(answer.body.revoked_grants ?? []));
    if (!answer.body.generation_ok) {
      discard(document, state, CLOSE.generationEnded);
      return true;
    }
    const ended = new Set(answer.body.ended_grants ?? []);
    if (ended.size > 0) await endSessions(document, documentName, state, ended);
    return false;
  }

  /** Grants whose login sessions ended (logout, expiry) while their people may still
   * edit: their edits are saved first, then their connections close with 4401. */
  async function endSessions(document, documentName, state, ended) {
    const unsaved = [...ended].some((grant) => state.dirty.has(grant));
    if (unsaved && !state.holding && !state.discarded) {
      try {
        await document.saveMutex.runExclusive(() => store(document, documentName, state));
      } catch (error) {
        if (!(error instanceof ApiUnavailable)) throw error; // still dirty: saved later
      }
    }
    for (const connection of document.getConnections()) {
      if (ended.has(connection.context.grant)) {
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

  /** The latest state cannot be stored: say so, with the kind of cause and the block
   * (the edits stay unsaved). */
  async function unrepresentable(document, state, written) {
    // Kind, block and the check's problem (a path or a node type, never page text, U10).
    const { problem, kind, block = null } = written;
    if (!state.unrepresentable) {
      log("live save refused", { page_id: state.pageId, kind, block, problem });
    }
    const notice = unrepresentableNotice(written);
    if (state.unrepresentable !== notice) tell(document, notice);
    state.unrepresentable = notice;
    try {
      await api.unrepresentable(state.pageId);
    } catch (error) {
      if (!(error instanceof ApiUnavailable)) throw error; // only the count is missing
    }
  }

  async function store(document, documentName, state) {
    const editors = [...state.dirty.keys()];
    if (editors.length === 0) return;
    // The state as it is now; the check runs on a worker (review M2 T9) while edits
    // may go on: those mark their sessions unsaved again.
    const json = yDocToJSON(document);
    const ydoc = Y.encodeStateAsUpdate(document);
    const snapshot = Buffer.from(Y.encodeSnapshot(Y.snapshot(document))).toString("base64");
    // Tables over the cell cap: too large, refused before a check worker is asked
    // (review M2 U2); the session goes on, so rows can be taken out again.
    const tables = tableLoad(json);
    if (tables.cells > MAX_TABLE_CELLS) {
      const problem = `${tables.cells} table cells`;
      return unrepresentable(document, state, { problem, kind: "tooLarge", block: tables.block });
    }
    for (const grant of editors) state.dirty.delete(grant);
    let written;
    try {
      written = await checks.readBack(json, state.size?.chars ?? 0);
    } catch (error) {
      if (!(error instanceof CheckFailed)) {
        for (const grant of editors) state.dirty.set(grant, true);
        throw error;
      }
      // Too heavy to check (the worker ran out of memory, or the check ran past its time
      // limit, review M4-1 P13): not stored, as a state that cannot be written.
      const kind = error instanceof CheckTimedOut ? "timeout" : "unknown";
      written = { ok: false, problem: error.message, kind, block: null };
    }
    if (!written.ok) {
      for (const grant of editors) state.dirty.set(grant, true);
      return unrepresentable(document, state, written);
    }
    // Unchanged from what was loaded (an edit undone, or a browser tidying the
    // document's structure): the stored Markdown stays exactly as it was written.
    const contentMd = written.markdown === state.baseline ? state.source : written.markdown;
    let answer;
    try {
      answer = await api.save(state.pageId, {
        generation: state.generation,
        ydoc,
        contentMd,
        editorGrants: editors,
        sessionKey: state.sessionKey,
      });
    } catch (error) {
      for (const grant of editors) state.dirty.set(grant, true);
      throw error;
    }
    if (answer.status === 200) {
      tell(document, `${STORED}${snapshot}`);
      if (state.unrepresentable) tell(document, REPRESENTABLE);
      state.unrepresentable = false;
      return;
    }
    if (answer.status === 409) return discard(document, state, CLOSE.generationEnded);
    if (answer.status === 403) {
      for (const grant of editors) state.dirty.set(grant, true); // still unsaved
      return endGeneration(document, documentName, state);
    }
    if (answer.status === 413) return discard(document, state, CLOSE.tooLarge);
    if (answer.status === 404) return discard(document, state, CLOSE.notFound);
    return discard(document, state, CLOSE.saveRefused);
  }

  return { discard, checkDocument, store };
}
