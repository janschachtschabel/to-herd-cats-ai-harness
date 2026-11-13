// Inline content (canonical runs, `canonical.mjs`) as Markdown that the page view's
// parser reads back as the same runs (review M2 S2). Marks nest by how far they reach
// (the longer one outside); bold is `**`, italic `_`, strike `~~`, so delimiters of
// different marks never merge into one run. A delimiter works only where CommonMark's
// flanking rules let it open or close; where they would not, the character outside it
// is written as a character reference (`**Hinweis:**&#x54;ext`), which reads as
// punctuation there.
import { WIKI_LINK, destination, title } from "./syntax.mjs";

// micromark's classes of the characters around a delimiter.
const PUNCTUATION = /^[\p{P}\p{S}]$/u;
const WHITESPACE = /^\s$/u;
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
    /^`|`$/.test(text) || (/^ /.test(text) && / $/.test(text) && /[^ ]/.test(text)) ? " " : "";
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

// CommonMark autolinks: `<https://example.org>`, `<anna@example.org>`.
const URI = /^[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>\p{Cc}]*$/u;
const EMAIL =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$/;

/** A link written as an autolink when its text is its address (`<https://…>`), the
 * way such links are usually written; null when it cannot be one. */
function autolink(key, run, inTable) {
  const [, href, linkTitle] = key.split("\u0000");
  if (linkTitle || run.t !== "text" || run.marks.includes("code")) return null;
  if (inTable && run.text.includes("|")) return null;
  if (run.text === href && URI.test(href)) return `<${href}>`;
  if (href === `mailto:${run.text}` && EMAIL.test(run.text)) return `<${run.text}>`;
  return null;
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
        ? { kind: "atom", gap: "close", out: linkEnd(key) }
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
    // A link over this run only, written as an autolink inside the other marks.
    const link = opening.find((key) => markType(key) === "link");
    const auto =
      link && reach(runs, index, link) === index + 1 ? autolink(link, run, inTable) : null;
    for (const key of opening) {
      if (auto && key === link) continue;
      if (markType(key) === "link") {
        out.push({ kind: "atom", gap: "open", out: "[" });
      } else out.push({ kind: "open", out: DELIMITER[key] });
      open.push(key);
    }
    if (auto) out.push({ kind: "atom", out: auto });
    else if (run.t === "br") out.push({ kind: "atom", out: "\\\n" });
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

const gapAt = (piece) =>
  piece?.kind === "text" ? piece.char === " " : piece?.kind === "atom" && piece.out === "\\\n";
const opens = (piece) => piece?.kind === "open" || piece?.gap === "open";
const closes = (piece) => piece?.kind === "close" || piece?.gap === "close";

/** Spaces and hard breaks just inside a delimiter or a link's brackets are moved
 * outside: a delimiter next to a space would not work, and the marks of a space or a
 * hard break are those of the text around it anyway (`canonical.mjs`). */
function moveGaps(list) {
  for (let moved = true; moved;) {
    moved = false;
    for (let i = 0; i + 1 < list.length; i++) {
      const swap =
        (opens(list[i]) && gapAt(list[i + 1])) || (gapAt(list[i]) && closes(list[i + 1]));
      if (swap) {
        [list[i], list[i + 1]] = [list[i + 1], list[i]];
        moved = true;
      }
    }
  }
  return list;
}

/** micromark's class of a character: 1 whitespace (or the edge of the block), 2
 * punctuation, 0 anything else. */
function kind(char) {
  if (char === undefined || WHITESPACE.test(char)) return 1;
  // micromark looks at UTF-16 code units: half of a surrogate pair is neither.
  if (char.codePointAt(0) > 0xffff) return 0;
  return PUNCTUATION.test(char) ? 2 : 0;
}

const lastChar = (piece) => (piece ? [...piece.out].at(-1) : undefined);
const firstChar = (piece) => (piece ? String.fromCodePoint(piece.out.codePointAt(0)) : undefined);

/** Whether the delimiter opens (or closes) with these characters around it. */
function works(piece, before, after) {
  const left = after !== 1 && (after !== 2 || before !== 0); // left-flanking
  const right = before !== 1 && (before !== 2 || after !== 0); // right-flanking
  const underscore = piece.out === "_";
  if (piece.kind === "open") return left && (!underscore || !right || before === 2);
  return right && (!underscore || !left || after === 2);
}

/** Each delimiter made to work: where it would not, the text character outside it is
 * written as a reference (punctuation to the parser). */
function flank(list) {
  list.forEach((piece, i) => {
    if (piece.kind !== "open" && piece.kind !== "close") return;
    const before = kind(lastChar(list[i - 1]));
    const after = kind(firstChar(list[i + 1]));
    if (works(piece, before, after)) return;
    const outside = piece.kind === "open" ? list[i - 1] : list[i + 1];
    if (outside?.kind === "text" && outside.char !== null) outside.out = reference(outside.char);
  });
  return list;
}

/** Last touches once every piece is written: a `!` right before `[` would start an
 * image; a bare `_` (`escaped`) must still stand between two letters or digits. */
function tidy(list) {
  list.forEach((piece, i) => {
    if (piece.kind !== "text" || piece.char === null) return;
    if (piece.out === "!" && list[i + 1]?.out.startsWith("[")) piece.out = "\\!";
    if (piece.out === "_") {
      const word =
        WORD.test(lastChar(list[i - 1]) ?? "") && WORD.test(firstChar(list[i + 1]) ?? "");
      if (!word) piece.out = "\\_";
    }
  });
  return list;
}

/** Canonical runs as Markdown. `table`: `|` is escaped in code too. */
export function writeInline(runs, { table = false } = {}) {
  return tidy(flank(moveGaps(pieces(runs, table))))
    .map((piece) => piece.out)
    .join("");
}
