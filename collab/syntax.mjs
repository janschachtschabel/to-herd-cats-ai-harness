// Markdown spelling helpers shared by the parser (`parse.mjs`) and the serializer
// (`serialize.mjs`, `inline.mjs`). Plain ESM without dependencies; the browser's live
// editor uses them too.

/** `[[Titel]]`: a link to another page by its title (found by `wikilinks.mjs`). */
export const WIKI_LINK = /\[\[([^\]\n]+)\]\]/g;

/** A link mark as one string (canonical form, `canonical.mjs`): href and title. */
export function linkKey(attrs) {
  return `link\u0000${attrs?.href ?? ""}\u0000${attrs?.title ?? ""}`;
}

/** `&` where it starts a character reference (`&amp;`, `&#169;`), which the parser
 * would decode. */
export const ENTITY = /&(?=#[0-9]{1,7};|#[xX][0-9a-fA-F]{1,6};|[A-Za-z][A-Za-z0-9]{0,31};)/g;

/** A link or image destination that reads back as the same URL: `<…>` when it holds
 * spaces, angle brackets, backslashes or unbalanced parentheses. */
export function destination(url) {
  const value = String(url ?? "");
  let depth = 0;
  for (const char of value) {
    depth += char === "(" ? 1 : char === ")" ? -1 : 0;
    if (depth < 0) break;
  }
  const plain = value.replace(ENTITY, "\\$&");
  if (value && depth === 0 && !/[\s<>\\\p{Cc}]/u.test(value)) return plain;
  return `<${value.replace(/[\\<>]/g, "\\$&").replace(ENTITY, "\\$&")}>`;
}

/** A link or image title in double quotes. */
export function title(value) {
  return `"${String(value).replace(/[\\"]/g, "\\$&").replace(ENTITY, "\\$&")}"`;
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
