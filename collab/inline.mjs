// Inline content (canonical runs, `canonical.mjs`) as Markdown that the page view's
// parser reads back as the same runs (review M2 S2). Marks nest by how far they reach
// (the longer one outside); bold is `**`, italic `_`, strike `~~`, so delimiters of
// different marks never merge into one run. A delimiter works only when the character
// outside it is a space, ASCII punctuation or the edge of the block; any other
// character there is written as a character reference (`**Hinweis:**&#84;ext`).
import { WIKI_LINK, destination, title } from "./syntax.mjs";

const PUNCTUATION = /^[!-/:-@[-`{-~]$/;
const DELIMITER = { bold: "**", italic: "_", strike: "~~" };
const ORDER = ["link", "bold", "italic", "strike"]; // outermost first on a tie
// Characters with a meaning in inline Markdown; `|` for tables, `@` for e-mail
// autolinks.
const SPECIAL = /[\\`*_[\]~<&|@]/;
// Whitespace the parser would read as such (or trim) where the editor has a
// character: written as references.
const ODD_SPACE = /[\p{White_Space}\p{Cc}]/u;

const reference = (char) =>
  char === " " ? "&nbsp;" : `&#x${char.codePointAt(0).toString(16).toUpperCase()};`;

const WORD = /[\p{L}\p{N}]/u;

/** One character of text as Markdown. */
function escaped(chars, i) {
  const char = chars[i];
  if (char === " ") return " ";
  // `_` between two letters or digits can neither open nor close emphasis.
  if (char === "_" && WORD.test(chars[i - 1] ?? "") && WORD.test(chars[i + 1] ?? "")) return char;
  if (SPECIAL.test(char)) return `\\${char}`;
  if (ODD_SPACE.test(char)) return reference(char);
  // Autolink literals the editor shows as text: `https\://`, `www\.`.
  if (char === ":" && chars[i + 1] === "/" && chars[i + 2] === "/") return "\\:";
  if (char === "." && /www$/i.test(chars.slice(Math.max(0, i - 3), i).join(""))) return "\\.";
  return char;
}

/** A wiki link as one run of text the page view finds as such (`wikilinks.mjs`): what
 * would be Markdown inside it is escaped; other characters stay as they are. */
function wikiLink(text) {
  const chars = [...text.slice(2, -2)];
  const inner = chars
    .map((char, i) => (char !== " " && ODD_SPACE.test(char) ? char : escaped(chars, i)))
    .join("");
  return `[[${inner}]]`;
}

/** Escaped text as units, one per character, so a unit next to a delimiter can be
 * written as a reference afterwards. A wiki link (`[[Titel]]`) is one unit, except in a
 * link's text (a link cannot hold another; there it is text). */
function textUnits(text, inLink) {
  const units = [];
  let last = 0;
  const plain = (part) => {
    const chars = [...part];
    chars.forEach((char, i) => units.push({ char, out: escaped(chars, i) }));
  };
  for (const match of inLink ? [] : text.matchAll(WIKI_LINK)) {
    plain(text.slice(last, match.index));
    units.push({ char: null, out: wikiLink(match[0]) });
    last = match.index + match[0].length;
  }
  plain(text.slice(last));
  return units;
}

function codeSpan(text, inTable) {
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(longest + 1);
  const pad =
    /^`|`$/.test(text) || (/^ /.test(text) && / $/.test(text) && text.trim() !== "") ? " " : "";
  const body = inTable ? text.replace(/\|/g, "\\|") : text;
  return `${fence}${pad}${body}${pad}${fence}`;
}

function altText(alt) {
  return [...alt].map((char) => (SPECIAL.test(char) || char === "!" ? `\\${char}` : char)).join("");
}

function image(run) {
  const src = destination(run.src);
  const text = altText(run.alt);
  return run.title ? `![${text}](${src} ${title(run.title)})` : `![${text}](${src})`;
}

function linkEnd(key) {
  const [, href, linkTitle] = key.split("\u0000");
  const target = destination(href);
  return linkTitle ? `](${target} ${title(linkTitle)})` : `](${target})`;
}

const markType = (key) => (key.startsWith("link\u0000") ? "link" : key);

/** How many runs from `index` on carry the mark. */
function reach(runs, index, key) {
  let end = index;
  while (end < runs.length && runs[end].marks.includes(key)) end++;
  return end;
}

/** The runs as pieces: text units, delimiters and atoms (code, images, breaks). */
function pieces(runs, inTable) {
  const out = [];
  const open = []; // mark keys, outermost first
  const close = (key) => {
    out.push(
      markType(key) === "link"
        ? { kind: "atom", out: linkEnd(key) }
        : { kind: "close", out: DELIMITER[key] },
    );
  };
  runs.forEach((run, index) => {
    const marks = run.marks.filter((key) => key !== "code");
    // Close down to the first open mark this run does not carry.
    const keep = open.findIndex((key) => !marks.includes(key));
    if (keep !== -1) for (const key of open.splice(keep).reverse()) close(key);
    const opening = marks
      .filter((key) => !open.includes(key))
      .sort(
        (a, b) =>
          reach(runs, index, b) - reach(runs, index, a) ||
          ORDER.indexOf(markType(a)) - ORDER.indexOf(markType(b)),
      );
    for (const key of opening) {
      if (markType(key) === "link") {
        // A `!` right before `[` would make the link an image.
        const previous = out.at(-1);
        if (previous?.kind === "text" && previous.out === "!") previous.out = "\\!";
        out.push({ kind: "atom", out: "[" });
      } else out.push({ kind: "open", out: DELIMITER[key] });
      open.push(key);
    }
    if (run.t === "br") out.push({ kind: "atom", out: "\\\n" });
    else if (run.t === "img") out.push({ kind: "atom", out: image(run) });
    else if (run.marks.includes("code"))
      out.push({ kind: "atom", out: codeSpan(run.text, inTable) });
    else {
      const inLink = run.marks.some((key) => markType(key) === "link");
      for (const unit of textUnits(run.text, inLink)) out.push({ kind: "text", ...unit });
    }
  });
  for (const key of open.reverse()) close(key);
  return out;
}

/** A delimiter works only next to a space, punctuation or the edge of the block. */
function flank(list) {
  list.forEach((piece, i) => {
    const outside =
      piece.kind === "open" ? list[i - 1] : piece.kind === "close" ? list[i + 1] : null;
    if (outside?.kind !== "text" || outside.char === null) return;
    const edge = piece.kind === "open" ? outside.out.at(-1) : outside.out[0];
    if (edge !== " " && !PUNCTUATION.test(edge)) outside.out = reference(outside.char);
  });
  return list;
}

/** Canonical runs as Markdown. `table`: `|` is escaped in code too. */
export function writeInline(runs, { table = false } = {}) {
  return flank(pieces(runs, table))
    .map((piece) => piece.out)
    .join("");
}
