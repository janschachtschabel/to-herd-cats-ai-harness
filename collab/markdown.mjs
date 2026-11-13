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
// for live editing at all.
import { getSchema } from "@tiptap/core";
import { prosemirrorJSONToYDoc, yDocToProsemirrorJSON } from "y-prosemirror";
import { difference, meaningOf } from "./meaning.mjs";
import { parseMarkdown } from "./parse.mjs";
import { RAW_MARKDOWN, extensions } from "./schema.mjs";
import { jsonToMarkdown } from "./serialize.mjs";

export { jsonToMarkdown };

export const FIELD = "default"; // the Y.XmlFragment the browser's Collaboration extension uses
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

/** Whether the block comes back from the editor meaning the same, and the editor can
 * show it as built. */
function survives(source) {
  const { json } = parseMarkdown(source);
  if (editorProblem(json) !== null) return false;
  return difference(meaningOf(source), meaningOf(jsonToMarkdown(json))) === null;
}

/** The editor's document for the Markdown (blocks it cannot show kept raw). */
export function markdownToJSON(markdown) {
  return parseMarkdown(normalized(markdown)).json;
}

/** The editor document for the Markdown, or `safe: false` when the editor would
 * change what the page means or could not show it as built (then it must not be
 * edited live). */
export function liveDocument(markdown) {
  const source = normalized(markdown);
  const meaning = meaningOf(source);
  const attempts = [() => false, (_, block) => !survives(block)];
  for (const keepRaw of attempts) {
    const { json } = parseMarkdown(source, keepRaw);
    if (editorProblem(json) !== null) continue;
    if (difference(meaning, meaningOf(jsonToMarkdown(json))) === null) return { safe: true, json };
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
