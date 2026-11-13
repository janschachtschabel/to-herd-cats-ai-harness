// Markdown <-> Yjs for live editing (spec 9: Markdown is canonical, Yjs is only the
// state of a live session). The editor's schema (`schema.mjs`) covers headings,
// paragraphs, bold, italic, strike, inline code, links, images, lists, task lists,
// quotes, code blocks, tables and rules. Anything else (raw HTML, reference links,
// footnotes, ...) is kept verbatim as a code block with the language `raw-markdown`
// and written back unchanged, so a live session never loses what it cannot show.
//
// Markdown is read with the page view's parser (`parse.mjs`) and written by
// `serialize.mjs`. Live editing must never change what a page means (review M2 R1):
// `liveDocument` converts the stored Markdown into the editor's document and back and
// compares both with the page view's parser (`meaning.mjs`). A block whose own
// conversion changes its meaning, or that the editor could not show as built, is kept
// as a raw block; if the page as a whole still comes back different, it is not opened
// for live editing at all. The document served is the one the browser's editor shows
// once loaded (`settle.mjs`): opening a page and leaving it sends nothing.
import { getSchema } from "@tiptap/core";
import { prosemirrorJSONToYDoc, yDocToProsemirrorJSON } from "@tiptap/y-tiptap";
import { FIELD } from "./editor.mjs";
import { difference, meaningOf } from "./meaning.mjs";
import { parseMarkdown } from "./parse.mjs";
import { RAW_MARKDOWN, extensions } from "./schema.mjs";
import { jsonToMarkdown } from "./serialize.mjs";
import { settle } from "./settle.mjs";

export { jsonToMarkdown };

export { FIELD };
export const RAW_LANGUAGE = RAW_MARKDOWN;

export const schema = getSchema(extensions());

export const normalized = (markdown) => markdown.replace(/\r\n?/g, "\n");

/** Why the browser's editor would not show the document as it is, or null (review M2
 * S1): it must be valid for the editor's schema (the browser drops what is not, and
 * that deletion would be saved), and it must come back unchanged from the Y.Doc. */
export function editorProblem(json) {
  // An empty page: the browser shows its own empty paragraph and adds it on typing.
  if (json?.type === "doc" && !json.content?.length) return null;
  let node;
  try {
    node = schema.nodeFromJSON(json);
    node.check();
  } catch (error) {
    return `invalid: ${error.message}`;
  }
  const back = yDocToProsemirrorJSON(prosemirrorJSONToYDoc(schema, json, FIELD), FIELD);
  return schema.nodeFromJSON(back).eq(node) ? null : "changed by the Y.Doc";
}

/** The document as the browser's editor shows it once loaded (`settle.mjs`, review M2
 * T1/T2): what its plugins change on loading is part of it, so opening a page and
 * leaving it sends nothing. Null when the browser would stop on it or would not leave
 * it alone. */
function settled(json, settleDoc) {
  let current = json;
  for (let round = 0; round < 2; round += 1) {
    const result = settleDoc(jsonToYDoc(current));
    if (result.invalid !== null) return null;
    if (result.update === null) return current;
    current = result.json;
  }
  return null;
}

/** Whether the block comes back from the editor meaning the same, and the editor can
 * show it as built. */
function survives(source) {
  const { json } = parseMarkdown(source);
  if (editorProblem(json) !== null) return false;
  return difference(meaningOf(source), meaningOf(jsonToMarkdown(json))) === null;
}

/** Whether the browser's editor, loading the block alone, leaves its meaning as is. */
function settlesAlone(source, settleDoc) {
  const shown = settled(parseMarkdown(source).json, settleDoc);
  return shown !== null && difference(meaningOf(source), meaningOf(jsonToMarkdown(shown))) === null;
}

/** The editor's document for the Markdown (blocks it cannot show kept raw). */
export function markdownToJSON(markdown) {
  return parseMarkdown(normalized(markdown)).json;
}

/** The editor document for the Markdown as the browser's editor shows it once loaded,
 * or `safe: false` when the editor would change what the page means or could not show
 * it as built (then it must not be edited live). A change the browser's editor makes
 * on loading is part of the document if it keeps the meaning; a block it would change
 * in meaning is kept raw. `settleDoc` is the headless browser editor (tests replace
 * it). */
export function liveDocument(markdown, { settleDoc = settle } = {}) {
  const source = normalized(markdown);
  let meaning = null;
  const attempts = [
    () => false,
    (_, block) => !survives(block),
    (_, block) => !survives(block) || !settlesAlone(block, settleDoc),
  ];
  for (const [attempt, keepRaw] of attempts.entries()) {
    const { json } = parseMarkdown(source, keepRaw);
    if (editorProblem(json) !== null) continue;
    const shown = settled(json, settleDoc);
    if (shown === null) continue;
    const written = jsonToMarkdown(shown);
    // The same text means the same: no need to read both (the usual case for a page
    // the live editor wrote).
    if (written === source) return { safe: true, json: shown, plain: attempt === 0 };
    meaning ??= meaningOf(source);
    if (difference(meaning, meaningOf(written)) === null) {
      return { safe: true, json: shown, plain: attempt === 0 };
    }
  }
  return { safe: false, json: null };
}

export function jsonToYDoc(json) {
  return prosemirrorJSONToYDoc(schema, json, FIELD);
}

export function markdownToYDoc(markdown) {
  return jsonToYDoc(markdownToJSON(markdown));
}

export function yDocToJSON(ydoc) {
  return yDocToProsemirrorJSON(ydoc, FIELD);
}

export function yDocToMarkdown(ydoc) {
  return jsonToMarkdown(yDocToJSON(ydoc));
}
