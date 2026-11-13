// Markdown spelling helpers shared by the parser (`parse.mjs`) and the serializer
// (`serialize.mjs`, `inline.mjs`). Plain ESM without dependencies; the browser's live
// editor uses them too.

/** `[[Titel]]`: a link to another page, resolved by the page view on the source text
 * outside code (frontend/src/features/wiki/markdown.ts `resolveWikiLinks`). */
export const WIKI_LINK = /\[\[([^\]\n]+)\]\]/g;

const FENCE = /^\s*(```|~~~)/;
const CODE_SPAN = /(?<!\\)(`+)[^`][\s\S]*?(?<!`)\1(?!`)|(`+)/g;

/** The Markdown with `replace` applied to the text outside fenced code and code spans,
 * line by line, the way the page view finds wiki links. */
export function outsideCode(markdown, replace) {
  let inFence = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (FENCE.test(line)) {
        inFence = !inFence;
        return line;
      }
      if (inFence) return line;
      let out = "";
      let last = 0;
      for (const match of line.matchAll(CODE_SPAN)) {
        if (match[2]) continue; // a lone backtick run is text
        out += replace(line.slice(last, match.index)) + match[0];
        last = match.index + match[0].length;
      }
      return out + replace(line.slice(last));
    })
    .join("\n");
}

/** A link mark as one string (canonical form, `canonical.mjs`): href and title. */
export function linkKey(attrs) {
  return `link\u0000${attrs?.href ?? ""}\u0000${attrs?.title ?? ""}`;
}

/** A link or image destination that reads back as the same URL: `<…>` when it holds
 * spaces, angle brackets, backslashes or unbalanced parentheses. */
export function destination(url) {
  const value = String(url ?? "");
  let depth = 0;
  for (const char of value) {
    depth += char === "(" ? 1 : char === ")" ? -1 : 0;
    if (depth < 0) break;
  }
  if (value && depth === 0 && !/[\s<>\\\p{Cc}]/u.test(value)) return value;
  return `<${value.replace(/[\\<>]/g, "\\$&")}>`;
}

/** A link or image title in double quotes. */
export function title(value) {
  return `"${String(value).replace(/[\\"]/g, "\\$&")}"`;
}

// A line of paragraph text that would start a block when read again: ATX heading,
// quote, bullet, ordered list item, setext underline or thematic break.
const BLOCK_START = [
  /^( {0,3})(#{1,6})(?=[ \t]|$)/,
  /^( {0,3})(>)/,
  /^( {0,3})([-+*])(?=[ \t]|$)/,
  /^( {0,3}\d{1,9})([.)])(?=[ \t]|$)/,
  /^( {0,3})(=+|-+)[ \t]*$/,
  /^( {0,3})([-*_])(?:[ \t]*\2){2,}[ \t]*$/,
];

/** A line of inline text that cannot be read as the start of another block: the
 * character that would start it is backslash-escaped (`\# kein Titel`, `2026\. …`). */
export function escapeBlockStart(line) {
  for (const pattern of BLOCK_START) {
    const match = pattern.exec(line);
    if (match) return `${match[1]}\\${line.slice(match[1].length)}`;
  }
  return line;
}
