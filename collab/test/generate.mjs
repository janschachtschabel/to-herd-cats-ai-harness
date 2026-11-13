// Random documents for the editor's schema (review M2 S2, S3): every node and mark
// type, nested lists, tables, code blocks in lists, images wherever inline content may
// stand, adjacent and overlapping marks, characters with a meaning in Markdown, and
// whitespace at the edges. Seeded, so a failure can be replayed.

/** A small seeded generator (mulberry32). */
export function seeded(seed) {
  let state = seed >>> 0;
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const int = (min, max) => min + Math.floor(next() * (max - min + 1));
  const pick = (list) => list[int(0, list.length - 1)];
  const chance = (p) => next() < p;
  return { next, int, pick, chance };
}

const WORDS = ["Text", "fett", "kursiv", "Größe", "Straße", "a", "b", "x1", "Ärger", "Ende"];
const PIECES = [
  ...WORDS,
  ...WORDS,
  " ",
  " ",
  " ",
  "  ",
  "\t",
  "\u00a0",
  "\u2003",
  "\n",
  ..."!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
  "**",
  "__",
  "~~",
  "```",
  "~~~",
  "1. ",
  "2026.",
  "1) ",
  "# ",
  "- ",
  "+ ",
  "> ",
  "---",
  "===",
  "    ",
  "|",
  "| --- |",
  "&copy;",
  "&#169;",
  "&nbsp;",
  "<div>",
  "<!-- x -->",
  "<https://example.org>",
  "https://example.org/mein_pfad_x",
  "www.example.org",
  "anna@example.org",
  "[[Seite]]",
  "[[API_Keys]]",
  "[[a *b*]]",
  "[a](b)",
  "![a](b)",
  "[^1]",
  "\\",
  "😀",
  "€",
  "»",
  "–",
  "\u200b",
  "\u0007",
];
const URLS = [
  "https://example.org",
  "/spaces/x/p/a",
  "https://de.wikipedia.org/wiki/Katze_(Tier)",
  "mein dokument.pdf",
  "a(b",
  "a)b",
  "https://example.org/<x>",
  "C:\\pfad",
  "#anker",
  "",
  "mailto:a@b.de",
];
const TITLES = [null, null, null, "Titel", 'Er sagte "ja"', "a \\ b", "(x)"];
const LANGUAGES = ["", "", "js", "bash", "python", "raw"];
const MARKS = ["bold", "italic", "strike", "code", "link"];

function text(r) {
  let out = "";
  const count = r.int(1, 5);
  for (let i = 0; i < count; i++) out += r.pick(PIECES);
  return out;
}

function marks(r) {
  const out = [];
  for (const type of MARKS) {
    if (!r.chance(type === "link" ? 0.15 : 0.25)) continue;
    if (type === "link") {
      const title = r.pick(TITLES);
      out.push({ type, attrs: { href: r.pick(URLS), ...(title && { title }) } });
    } else out.push({ type });
  }
  return out;
}

function withMarks(node, list) {
  return list.length ? { ...node, marks: list } : node;
}

function inline(r, { breaks }) {
  const out = [];
  const count = r.int(0, 6);
  for (let i = 0; i < count; i++) {
    const kind = r.next();
    if (kind < 0.12) {
      const title = r.pick(TITLES);
      const attrs = { src: r.pick(URLS) || "x.png", alt: r.chance(0.8) ? text(r) : null, title };
      out.push({ type: "image", attrs }); // images carry no marks (schema.mjs)
    } else if (kind < 0.2 && breaks) {
      out.push({ type: "hardBreak" });
    } else {
      out.push(withMarks({ type: "text", text: text(r) }, marks(r)));
    }
  }
  return out;
}

function codeText(r) {
  const lines = [];
  const count = r.int(0, 4);
  for (let i = 0; i < count; i++) {
    lines.push(
      r.pick(["x = 1", "", "```", "````js", "~~~", "  eingerückt", "a|b", "<div>", "\t$ npm ci"]),
    );
  }
  return lines.join("\n") + (r.chance(0.2) ? "\n" : "");
}

function paragraph(r, { empty = 0.08 } = {}) {
  if (r.chance(empty)) return { type: "paragraph", content: [] };
  return { type: "paragraph", content: inline(r, { breaks: true }) };
}

function items(r, depth, type) {
  const out = [];
  const count = r.int(1, 3);
  for (let i = 0; i < count; i++) {
    const content = [paragraph(r, { empty: 0.25 })];
    const more = depth < 3 ? r.int(0, 2) : 0;
    for (let j = 0; j < more; j++) content.push(block(r, depth + 1));
    const item = { type, content };
    if (type === "taskItem") item.attrs = { checked: r.chance(0.5) };
    out.push(item);
  }
  return out;
}

/** Code in a table cell cannot hold a backslash right before `|`: GFM reads `\|` there
 * as an escaped pipe and `\\|` as the end of the cell, so no Markdown says it. The save
 * check refuses such a document (test/typed.test.mjs); the generator leaves it out. */
function cellSafe(node) {
  if (!node.marks?.some((mark) => mark.type === "code")) return node;
  // Control characters are dropped on saving (`canonical.mjs`), so one between the two
  // does not keep them apart.
  // eslint-disable-next-line no-control-regex -- control characters are what it skips
  return { ...node, text: node.text.replace(/\\(?=[\u0000-\u001f\u007f-\u009f]*\|)/g, "/") };
}

function table(r) {
  const columns = r.int(1, 4);
  const align = Array.from({ length: columns }, () =>
    r.pick([null, null, "left", "right", "center"]),
  );
  // A row added in the editor (Tab in the last cell) has no alignment of its own until
  // the editor gives it its columns' (review M2 T3): the save check reads it so.
  const row = (type, added = false) => ({
    type: "tableRow",
    content: align.map((value) => ({
      type,
      attrs: { align: added ? null : value },
      content: [{ type: "tableParagraph", content: inline(r, { breaks: false }).map(cellSafe) }],
    })),
  });
  const rows = [row("tableHeader")];
  const body = r.int(0, 3);
  for (let i = 0; i < body; i++) rows.push(row("tableCell", r.chance(0.2)));
  return { type: "table", content: rows };
}

function block(r, depth) {
  const kind = r.next();
  const nested = depth < 3;
  if (kind < 0.35) return paragraph(r);
  if (kind < 0.45) {
    return {
      type: "heading",
      attrs: { level: r.int(1, 6) },
      content: inline(r, { breaks: false }),
    };
  }
  if (kind < 0.55) {
    const textContent = codeText(r);
    return {
      type: "codeBlock",
      attrs: { language: r.pick(LANGUAGES) || null },
      content: textContent ? [{ type: "text", text: textContent }] : [],
    };
  }
  if (kind < 0.6) return { type: "horizontalRule" };
  if (kind < 0.68 && nested) {
    const content = Array.from({ length: r.int(1, 2) }, () => block(r, depth + 1));
    return { type: "blockquote", content };
  }
  if (kind < 0.76 && nested) return { type: "bulletList", content: items(r, depth, "listItem") };
  if (kind < 0.84 && nested) {
    const start = r.pick([1, 1, 1, 0, 3, 10, 99, 999999999]);
    return { type: "orderedList", attrs: { start }, content: items(r, depth, "listItem") };
  }
  if (kind < 0.9 && nested) return { type: "taskList", content: items(r, depth, "taskItem") };
  if (kind < 0.96) return table(r);
  return paragraph(r);
}

/** A random document of the editor's schema. */
export function generateDocument(r) {
  const content = Array.from({ length: r.int(1, 6) }, () => block(r, 0));
  return { type: "doc", content };
}
