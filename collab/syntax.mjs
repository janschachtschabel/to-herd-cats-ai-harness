// Markdown spelling helpers for the editor's serializer (`schema.mjs`): what Tiptap's
// serializer writes would otherwise mean something else when read again (review M2 R1).
// Plain ESM without dependencies; the browser's live editor uses it too.

/** A link or image destination that reads back as the same URL: `<…>` when it holds
 * spaces, angle brackets, backslashes or unbalanced parentheses. */
export function destination(url) {
  const value = String(url ?? "");
  let depth = 0;
  for (const char of value) {
    depth += char === "(" ? 1 : char === ")" ? -1 : 0;
    if (depth < 0) break;
  }
  if (depth === 0 && !/[\s<>\\]/.test(value)) return value;
  return `<${value.replace(/[\\<>]/g, "\\$&")}>`;
}

/** A link or image title in double quotes. */
export function title(value) {
  return `"${String(value).replace(/[\\"]/g, "\\$&")}"`;
}

/** Image alt text (the serializer writes it unescaped). */
export function altText(value) {
  return String(value ?? "").replace(/[\\[\]]/g, "\\$&");
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

/** Paragraph text whose lines cannot be read as the start of another block: the
 * first character of such a line is backslash-escaped (`\# kein Titel`, `2026\. …`). */
export function escapeBlockStarts(markdown) {
  return markdown
    .split("\n")
    .map((line) => {
      for (const pattern of BLOCK_START) {
        const match = pattern.exec(line);
        if (match) return `${match[1]}\\${line.slice(match[1].length)}`;
      }
      return line;
    })
    .join("\n");
}

const ESCAPED_WIKI_LINK = /\\\[\\\[([^\n]+?)\\\]\\\]/g; // `\[\[Titel\]\]`
const FENCE = /^\s*(```|~~~)/;
const CODE_SPAN = /(?<!\\)(`+)[^`][\s\S]*?(?<!`)\1(?!`)|(`+)/g;

function unescapeWikiLinks(text) {
  // The serializer escapes `_`, `*`, `~`, `` ` `` and `\` inside the title too; the
  // page view looks the page up by the title as written.
  return text.replace(
    ESCAPED_WIKI_LINK,
    (_, inner) => `[[${inner.replace(/\\([\\`*_~])/g, "$1")}]]`,
  );
}

/** The serializer escapes brackets, which would turn `[[Titel]]` (a link to another
 * page, resolved by the browser) into literal text: wiki links are written back as
 * they came, outside fenced code and code spans. */
export function keepWikiLinks(markdown) {
  let inFence = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (FENCE.test(line)) inFence = !inFence;
      else if (!inFence) {
        let out = "";
        let last = 0;
        for (const match of line.matchAll(CODE_SPAN)) {
          out += unescapeWikiLinks(line.slice(last, match.index)) + match[0];
          last = match.index + match[0].length;
        }
        return out + unescapeWikiLinks(line.slice(last));
      }
      return line;
    })
    .join("\n");
}
