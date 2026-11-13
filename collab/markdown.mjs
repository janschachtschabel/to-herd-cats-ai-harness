// Markdown <-> Yjs for live editing (spec 9: Markdown is canonical, Yjs is only the
// state of a live session). The editor's schema (`schema.mjs`) covers headings,
// paragraphs, bold, italic, strike, inline code, links, images, lists, task lists,
// quotes, code blocks, tables and rules. Anything else (raw HTML, reference links,
// footnotes, ...) is kept verbatim as a code block with the language `raw-markdown`
// and written back unchanged, so a live session never loses what it cannot show.
import { getSchema } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { Lexer } from "marked";
import { prosemirrorJSONToYDoc, yDocToProsemirrorJSON } from "y-prosemirror";
import { RAW_MARKDOWN, extensions, keepWikiLinks } from "./schema.mjs";

export const FIELD = "default"; // the Y.XmlFragment the browser's Collaboration extension uses
export const RAW_LANGUAGE = RAW_MARKDOWN;

const schema = getSchema(extensions());
const manager = new MarkdownManager({ extensions: extensions() });

const BLOCKS = new Set(["space", "heading", "paragraph", "list", "list_item", "blockquote"]);
const OTHER = new Set(["code", "table", "hr", "text", "checkbox", "br", "escape"]);
const INLINE = new Set(["strong", "em", "del", "codespan", "link", "image"]);
const FOOTNOTE = /\[\^[^\]\s]+\]/; // `[^1]`: a footnote, which the editor does not know

/** Whether the editor can represent the token (and everything inside it). */
function representable(token) {
  if (!token || typeof token !== "object") return true;
  if (token.type !== undefined) {
    if (!BLOCKS.has(token.type) && !OTHER.has(token.type) && !INLINE.has(token.type)) return false;
    if ((token.type === "link" || token.type === "image") && !inlineLink(token)) return false;
    if (token.type === "text" && FOOTNOTE.test(token.raw ?? "")) return false;
  }
  for (const [key, value] of Object.entries(token)) {
    if (key === "raw" || key === "text") continue;
    if (Array.isArray(value) && !value.every(representableValue)) return false;
  }
  return true;
}

function representableValue(value) {
  if (Array.isArray(value)) return value.every(representableValue); // table rows
  return typeof value !== "object" || value === null || representable(value);
}

/** `[a](b)`, `<b>` and bare URLs; a reference link (`[a][ref]`) needs its definition. */
function inlineLink(token) {
  const raw = token.raw ?? "";
  return raw.endsWith(")") || raw.startsWith("<") || raw === token.href;
}

function fence(text) {
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map((run) => run.length));
  return "`".repeat(Math.max(3, longest + 1));
}

/** The Markdown with every block the editor cannot represent wrapped as a raw block. */
function protect(markdown) {
  const tokens = new Lexer({ gfm: true }).lex(markdown);
  if (tokens.map((t) => t.raw).join("") !== markdown) return markdown; // never guess
  return tokens
    .map((token) => {
      if (token.type === "space" || representable(token)) return token.raw;
      const body = token.raw.replace(/\n+$/, "");
      const trailing = token.raw.slice(body.length);
      const marks = fence(body);
      return `${marks}${RAW_LANGUAGE}\n${body}\n${marks}${trailing || "\n"}`;
    })
    .join("");
}

export function markdownToJSON(markdown) {
  return manager.parse(protect(markdown.replace(/\r\n?/g, "\n")));
}

export function jsonToMarkdown(json) {
  // tables bring their own blank lines
  return keepWikiLinks(manager.serialize(json).replace(/^\n+|\n+$/g, ""));
}

export function markdownToYDoc(markdown) {
  return prosemirrorJSONToYDoc(schema, markdownToJSON(markdown), FIELD);
}

export function yDocToMarkdown(ydoc) {
  return jsonToMarkdown(yDocToProsemirrorJSON(ydoc, FIELD));
}
