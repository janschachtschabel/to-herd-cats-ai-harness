// The heavy checks of live editing, in a worker thread (review M2 T9): reading a page's
// Markdown into the editor's document, settling it as the browser's editor would, and
// the save check take seconds on a page of 200,000 characters. On the collab process's
// event loop they froze every other live document meanwhile. `checks.mjs` sends the
// work here; each answer is the same as the functions' own.
import { parentPort } from "node:worker_threads";
import * as Y from "yjs";
import { FIELD } from "./editor.mjs";
import {
  editorProblem,
  jsonToMarkdown,
  jsonToYDoc,
  liveDocument,
  yDocToJSON,
  yDocToMarkdown,
} from "./markdown.mjs";
import { sameMeaning } from "./meaning.mjs";
import { readBack } from "./readback.mjs";
import { settle } from "./settle.mjs";

/** The Markdown as the live document: its Yjs state and the Markdown it is written as
 * (the baseline), or `safe: false`. */
export function open(markdown) {
  const converted = liveDocument(markdown);
  if (!converted.safe) return { safe: false };
  const ydoc = jsonToYDoc(converted.json);
  return { safe: true, update: Y.encodeStateAsUpdate(ydoc), baseline: yDocToMarkdown(ydoc) };
}

/** A stored live state as the browser's editor will show it: `{ problem }` when it
 * would not be shown as it is, else the update that tidies it (or null) and the
 * baseline. */
export function tidy(stored) {
  const ydoc = new Y.Doc();
  Y.applyUpdate(ydoc, stored);
  const before = Y.encodeStateVector(ydoc);
  if (editorProblem(yDocToJSON(ydoc)) !== null) return { problem: "invalid" };
  const shown = settle(ydoc);
  if (shown.invalid !== null) return { problem: "invalid" };
  let changed = false;
  if (shown.update !== null) {
    if (!sameMeaning(yDocToMarkdown(ydoc), jsonToMarkdown(shown.json)))
      return { problem: "meaning" };
    Y.applyUpdate(ydoc, shown.update);
    changed = true;
  }
  // An empty shared document stops the browser once someone undoes their first
  // paragraph (review M2 T6): it holds one empty paragraph, as a built one does.
  const fragment = ydoc.getXmlFragment(FIELD);
  if (fragment.length === 0) {
    fragment.insert(0, [new Y.XmlElement("paragraph")]);
    changed = true;
  }
  const update = changed ? Y.encodeStateAsUpdate(ydoc, before) : null;
  return { problem: null, update, baseline: yDocToMarkdown(ydoc) };
}

export const WORK = { open, tidy, readBack };

parentPort?.on("message", ({ id, kind, payload }) => {
  try {
    parentPort.postMessage({ id, result: WORK[kind](payload) });
  } catch (error) {
    parentPort.postMessage({ id, error: { message: error.message, stack: error.stack } });
  }
});
