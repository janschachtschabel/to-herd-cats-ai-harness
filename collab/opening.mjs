// Opening a page into a live document (`live.mjs` onLoadDocument): the stored Markdown or
// live state is loaded through the API, checked on a check worker (`checks.mjs`) and
// built as the browser's editor shows it; what cannot be shown faithfully is refused
// (4422), what is too large or too heavy to check is refused (4413), and past the memory
// budget of loaded documents (`memory.mjs`) nothing more is built (4507).
import { randomUUID } from "node:crypto";
import * as Y from "yjs";
import { MAX_TABLE_CELLS, markdownTableCells } from "./cells.mjs";
import { CheckFailed, CheckTimedOut } from "./checks.mjs";
import { documentEstimate, pageEstimate } from "./memory.mjs";
import { CLOSE, deny } from "./protocol.mjs";

export const DENIAL = {
  401: CLOSE.unauthorized,
  403: CLOSE.forbidden,
  404: CLOSE.notFound,
  413: CLOSE.tooLarge,
};

export function openRules({ api, log, checks, size, live, memory }) {
  /** Load the page into `document`; its state goes into `live` under `documentName`.
   * Throws (and closes the connection) when it must not be opened. */
  async function load(document, documentName, context) {
    const answer = await api.load(context.pageId, context.grant, context.generation);
    if (answer.status === 409) throw deny(context, CLOSE.generationEnded);
    if (answer.status !== 200) throw deny(context, DENIAL[answer.status] ?? CLOSE.forbidden);
    const { generation, ydoc_b64: stored, content_md: contentMd } = answer.body;
    const state = { pageId: context.pageId, generation, sessionKey: randomUUID() };
    Object.assign(state, { dirty: new Map(), seen: new Set(), discarded: false, holding: false });
    // Tables of more cells than the cap are too large for live editing: refused before
    // a check worker is asked (review M2 U2).
    const cells = markdownTableCells(contentMd);
    if (cells > MAX_TABLE_CELLS) {
      log("live page too large", { page_id: context.pageId, table_cells: cells });
      throw deny(context, CLOSE.tooLarge);
    }
    // Past the memory budget of loaded documents the page is not built (review M4-1 P12):
    // "busy", try again shortly or edit as Markdown. Given back in `live.mjs` when the
    // document is unloaded or not loaded after all.
    const storedBytes = stored ? Math.floor((stored.length * 3) / 4) : 0;
    const estimate = pageEstimate({ storedBytes, chars: contentMd.length, cells });
    if (!memory.reserve(documentName, estimate)) {
      log("live editor busy", { page_id: context.pageId, estimate, used: memory.used });
      throw deny(context, CLOSE.busy);
    }
    // The heavy work runs on a check worker (`checks.mjs`, review M2 T9), smaller pages
    // first (U6). A page too heavy to check there is too large for live editing.
    const check = (work) =>
      work.catch((error) => {
        if (!(error instanceof CheckFailed)) throw error;
        // No message: no page text.
        const reason =
          error instanceof CheckTimedOut ? "timeout" : (error.cause?.code ?? "check_failed");
        log("live check failed", { page_id: context.pageId, reason });
        throw deny(context, CLOSE.tooLarge);
      });
    let opened;
    if (stored) {
      // A state the browser's editor would repair (and save repaired) is not opened;
      // one it would only tidy without changing its meaning is tidied, so the browser
      // has nothing left to change (review M2 T1, ruling A).
      const bytes = Buffer.from(stored, "base64");
      opened = await check(checks.tidy(bytes, contentMd.length));
      if (opened.problem !== null) throw deny(context, CLOSE.notRoundTripSafe);
      Y.applyUpdate(document, bytes);
    } else {
      // Only a page the editor can show without changing its meaning is opened, as the
      // browser's editor shows it once loaded.
      opened = await check(checks.open(contentMd, contentMd.length));
      if (!opened.safe) throw deny(context, CLOSE.notRoundTripSafe);
    }
    const tidied = opened.update !== null;
    if (tidied) Y.applyUpdate(document, opened.update);
    // A joining browser gets the whole state in one message: over the limit, it would
    // never arrive (review M2 U3).
    state.size = size.measure(document);
    if (!size.fits(state.size)) {
      log("live page too large", { page_id: context.pageId, state_bytes: state.size.bytes });
      throw deny(context, CLOSE.tooLarge);
    }
    if (tidied) {
      // Built or tidied here: saved at once (content unchanged, so no version), so a
      // browser that reconnects later meets the same Yjs history.
      const saved = await api.save(context.pageId, {
        generation,
        ydoc: Y.encodeStateAsUpdate(document),
        contentMd,
        editorGrants: [context.grant],
        sessionKey: state.sessionKey,
      });
      if (saved.status === 409) throw deny(context, CLOSE.generationEnded);
      if (saved.status !== 200) throw deny(context, DENIAL[saved.status] ?? CLOSE.forbidden);
    }
    memory.settle(documentName, documentEstimate({ stateBytes: state.size.bytes, cells }));
    state.source = contentMd;
    state.baseline = opened.baseline;
    live.set(documentName, state);
  }

  return { load };
}
