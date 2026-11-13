// The canonical form of an editor document: what the people in the editor see, with
// what Markdown cannot say and the page view does not show taken out (review M2 S2).
// The serializer writes this form, and a save is checked by comparing the canonical
// form of the document with that of the Markdown read back. What is dropped:
// - runs of spaces, tabs and line breaks in text become one space, and there is none
//   at the start or end of a text block or next to a hard break (the page view
//   collapses and trims them); bold, italic, strike and link on such a space follow
//   the text around it (invisible on a space);
// - a hard break at the end of a text block (Markdown has none there);
// - an empty paragraph after a non-empty block (one blank line is the gap between
//   blocks; further empty ones become `&nbsp;` paragraphs), the empty first paragraph
//   of a list item (the item starts with its next block); an empty task item keeps a
//   `&nbsp;` paragraph (the checkbox needs text after it);
// - control characters other than tab and line breaks in text (see CONTROL);
// - attributes without Markdown: image size, link target/rel/class, list type, column
//   width; bold, italic, strike and code on an image (invisible).

import { linkKey } from "./syntax.mjs";

export const NBSP = " ";
const SPACE = /^[ \t\n\r]$/;
// Control characters other than tab and line breaks: invisible in the editor, and
// Markdown has no way to write them (the parser turns a reference to one into U+FFFD).
// eslint-disable-next-line no-control-regex -- control characters are what it finds
const CONTROL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g;
const ON_IMAGE = new Set(["link"]);

function markKeys(marks, allowed) {
  const keys = (marks ?? [])
    .filter((mark) => !allowed || allowed.has(mark.type))
    .map((mark) => (mark.type === "link" ? linkKey(mark.attrs) : mark.type));
  return [...new Set(keys)].sort();
}

/** One item per character, hard break and image. */
function atoms(content) {
  const out = [];
  for (const node of content ?? []) {
    if (node.type === "text") {
      const marks = markKeys(node.marks);
      const code = marks.includes("code");
      for (const char of String(node.text ?? "").replace(CONTROL, "")) {
        if (!code && SPACE.test(char)) out.push({ t: "space", marks: [] });
        else out.push({ t: "char", char: code && /[\n\r]/.test(char) ? " " : char, marks });
      }
    } else if (node.type === "hardBreak") {
      out.push({ t: "br", marks: markKeys(node.marks) });
    } else if (node.type === "image") {
      const { src, alt, title } = node.attrs ?? {};
      out.push({
        t: "img",
        src: src ?? "",
        alt: alt ?? "",
        title: title ?? "",
        marks: markKeys(node.marks, ON_IMAGE),
      });
    } else {
      out.push({ t: "other", type: node.type });
    }
  }
  return out;
}

const shared = (a, b) => a.filter((key) => b.includes(key));
const isGap = (atom) => atom.t === "space" || atom.t === "br";

/** Spaces collapsed and trimmed, trailing hard breaks dropped, the marks of spaces and
 * hard breaks taken from their neighbours. */
function tidy(list) {
  const out = [];
  for (const atom of list) {
    if (atom.t === "space" && (out.length === 0 || isGap(out.at(-1)))) continue;
    if (atom.t === "br" && out.at(-1)?.t === "space") out.pop();
    out.push(atom);
  }
  for (;;) {
    const last = out.at(-1);
    if (last && isGap(last)) out.pop();
    else break;
  }
  for (let i = 0; i < out.length; i++) {
    if (!isGap(out[i])) continue;
    const before = out[i - 1];
    let j = i + 1;
    while (j < out.length && isGap(out[j])) j++;
    const after = out[j];
    const marks = before && after ? shared(before.marks, after.marks) : [];
    out[i] = { ...out[i], marks: marks.filter((key) => key !== "code") };
  }
  return out;
}

/** Atoms merged into runs: text with the same marks, hard breaks, images. */
function runs(list) {
  const out = [];
  for (const atom of list) {
    if (atom.t === "char" || atom.t === "space") {
      const text = atom.t === "space" ? " " : atom.char;
      const last = out.at(-1);
      if (last?.t === "text" && last.marks.join("\n") === atom.marks.join("\n")) {
        last.text += text;
      } else out.push({ t: "text", text, marks: atom.marks });
    } else if (atom.t === "br") {
      out.push({ t: "br", marks: atom.marks });
    } else {
      const { t, ...rest } = atom;
      out.push({ t, ...rest });
    }
  }
  return out;
}

/** The canonical inline content of a text block. */
export function inlineOf(content) {
  return runs(tidy(atoms(content)));
}

function cell(node) {
  const attrs = node.attrs ?? {};
  const paragraphs = (node.content ?? []).map((child) => ({
    type: child.type,
    inline: inlineOf(child.content),
  }));
  return {
    type: node.type,
    align: attrs.align ?? null,
    colspan: attrs.colspan ?? 1,
    rowspan: attrs.rowspan ?? 1,
    content: paragraphs,
  };
}

const emptyParagraph = (block) => block.type === "paragraph" && block.inline.length === 0;
const nbspParagraph = () => ({
  type: "paragraph",
  inline: [{ t: "text", text: NBSP, marks: [] }],
});

/** Blocks of a container with the empty-paragraph rule applied. */
function blocks(content, container) {
  const out = [];
  const converted = (content ?? []).map(blockOf);
  converted.forEach((block, index) => {
    if (!emptyParagraph(block)) return out.push(block);
    const previous = converted[index - 1];
    if (index === 0 && container === "taskItem") return out.push(nbspParagraph());
    if (previous && emptyParagraph(previous)) out.push(nbspParagraph());
  });
  return out;
}

/** The canonical form of a block node. */
export function blockOf(node) {
  const attrs = node.attrs ?? {};
  switch (node.type) {
    case "paragraph":
    case "tableParagraph":
      return { type: node.type, inline: inlineOf(node.content) };
    case "heading":
      return { type: "heading", level: attrs.level ?? 1, inline: inlineOf(node.content) };
    case "codeBlock":
      return {
        type: "codeBlock",
        language: attrs.language || "",
        text: (node.content ?? []).map((child) => child.text ?? "").join(""),
      };
    case "horizontalRule":
      return { type: "horizontalRule" };
    case "blockquote":
    case "listItem":
    case "taskItem":
    case "doc": {
      const out = { type: node.type, content: blocks(node.content, node.type) };
      if (node.type === "taskItem") out.checked = Boolean(attrs.checked);
      return out;
    }
    case "bulletList":
    case "taskList":
      return { type: node.type, content: (node.content ?? []).map(blockOf) };
    case "orderedList":
      return { type: node.type, start: attrs.start ?? 1, content: node.content.map(blockOf) };
    case "table":
      return {
        type: "table",
        content: (node.content ?? []).map((row) => ({
          type: row.type,
          content: (row.content ?? []).map(cell),
        })),
      };
    default:
      return { type: node.type, attrs, content: (node.content ?? []).map(blockOf) };
  }
}

/** The canonical form of an editor document (JSON). */
export function canonical(doc) {
  return blockOf(doc);
}
