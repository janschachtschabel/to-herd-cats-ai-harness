// Markdown <-> Yjs for live editing (spec 9: Markdown is canonical, Yjs is only the
// state of a live session). The editor's schema (`schema.mjs`) covers headings,
// paragraphs, bold, italic, strike, inline code, links, images, lists, task lists,
// quotes, code blocks, tables and rules. Anything else (raw HTML, reference links,
// footnotes, linked images, ...) is kept verbatim as a code block with the language
// `raw-markdown` and written back unchanged, so a live session never loses what it
// cannot show.
//
// Live editing must never change what a page means (review M2 R1). `liveDocument`
// converts the stored Markdown into the editor's document and back and compares both
// with the page view's parser (`meaning.mjs`). A block whose own conversion changes
// its meaning is kept as a raw block; if the page as a whole still comes back
// different, it is not opened for live editing at all.
import { getSchema } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { decodeNamedCharacterReference } from "decode-named-character-reference";
import { Lexer, Marked } from "marked";
import { prosemirrorJSONToYDoc, yDocToProsemirrorJSON } from "y-prosemirror";
import { difference, meaningOf } from "./meaning.mjs";
import { RAW_MARKDOWN, extensions, keepWikiLinks } from "./schema.mjs";

export const FIELD = "default"; // the Y.XmlFragment the browser's Collaboration extension uses
export const RAW_LANGUAGE = RAW_MARKDOWN;

const ENTITY = /^&(?:#[xX]([0-9a-fA-F]{1,6})|#(\d{1,7})|([A-Za-z][A-Za-z0-9]{0,31}));/;

/** `&copy;`, `&#169;`, `&#xA9;` as the character they stand for (CommonMark), so the
 * editor shows `©` and writes it back as such; unknown names stay text. */
const entities = {
  extensions: [
    {
      name: "entity",
      level: "inline",
      start: (src) => src.indexOf("&"),
      tokenizer(src) {
        const match = ENTITY.exec(src);
        if (!match) return undefined;
        let text;
        if (match[3]) text = decodeNamedCharacterReference(match[3]);
        else {
          const code = parseInt(match[1] ?? match[2], match[1] ? 16 : 10);
          const valid = code > 0 && code <= 0x10ffff && (code < 0xd800 || code > 0xdfff);
          text = String.fromCodePoint(valid ? code : 0xfffd);
        }
        if (text === false) return undefined;
        return { type: "text", raw: match[0], text };
      },
    },
  ],
};

const schema = getSchema(extensions());
const manager = new MarkdownManager({
  marked: new Marked({ gfm: true }).use(entities),
  extensions: extensions(),
});

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
    if (token.type === "link" && token.tokens?.some((t) => t.type === "image")) return false;
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

function rawBlock(token) {
  const body = token.raw.replace(/\n+$/, "");
  const trailing = token.raw.slice(body.length);
  const marks = fence(body);
  return `${marks}${RAW_LANGUAGE}\n${body}\n${marks}${trailing || "\n"}`;
}

function convert(markdown) {
  return jsonToMarkdown(manager.parse(markdown));
}

/** Whether the block comes back from the editor meaning the same. */
function survives(raw) {
  return difference(meaningOf(raw), meaningOf(convert(raw))) === null;
}

/** The Markdown with every block the editor cannot represent wrapped as a raw block;
 * `strict` also wraps every block whose own conversion changes its meaning. */
function protect(markdown, { strict = false } = {}) {
  const tokens = new Lexer({ gfm: true }).lex(markdown);
  if (tokens.map((t) => t.raw).join("") !== markdown) return markdown; // never guess
  return tokens
    .map((token) => {
      if (token.type === "space") return token.raw;
      if (representable(token) && (!strict || survives(token.raw))) return token.raw;
      return rawBlock(token);
    })
    .join("");
}

const normalized = (markdown) => markdown.replace(/\r\n?/g, "\n");

export function markdownToJSON(markdown) {
  return manager.parse(protect(normalized(markdown)));
}

export function jsonToMarkdown(json) {
  // tables bring their own blank lines
  return keepWikiLinks(manager.serialize(json).replace(/^\n+|\n+$/g, ""));
}

/** The editor document for the Markdown, or `safe: false` when the editor would
 * change what the page means (then it must not be edited live). */
export function liveDocument(markdown) {
  const source = normalized(markdown);
  const meaning = meaningOf(source);
  for (const strict of [false, true]) {
    const json = manager.parse(protect(source, { strict }));
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

export function yDocToMarkdown(ydoc) {
  return jsonToMarkdown(yDocToProsemirrorJSON(ydoc, FIELD));
}
