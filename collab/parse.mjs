// Markdown → the editor's document, read with the page view's own parser (review M2
// S2/S3): micromark with the GFM extensions builds the syntax tree that react-markdown
// renders, and that tree is turned into the editor's nodes. One parser for the page
// view, the live editor and the save check, so the editor never reads a page
// differently from the page view.
//
// A top-level block holding what the editor cannot show (raw HTML, reference links
// and definitions, footnotes, images the page view does not show, ...) becomes a raw block (`raw-markdown` code block)
// with exactly its source text, written back unchanged.
import { fromMarkdown } from "mdast-util-from-markdown";
import { gfmFromMarkdown } from "mdast-util-gfm";
import { gfm } from "micromark-extension-gfm";
import { RAW_MARKDOWN, allowedUri } from "./schema.mjs";
import { replaceWikiLinks } from "./wikilinks.mjs";

// `[[Titel]]` while parsing: a link `[…]()` of the same length whose text is
// private-use characters. Like the page view's `[Titel](wiki:…)` it is a link of its
// own (it ends the text around it, so an address before it is linked the same way) and
// punctuation at both ends; it is restored as the title's text afterwards.
const HOLE = "\ue000";
const ESCAPE = /\\([!-/:-@[-`{-~])/g;

const UNSUPPORTED = new Set([
  "html",
  "definition",
  "footnoteDefinition",
  "footnoteReference",
  "linkReference",
  "imageReference",
  "yaml",
]);

/** Whether the editor can represent the node and everything inside it. An image the
 * page view does not show (its source is not http, https, mailto or relative) is not
 * shown as an image in the editor either (review M2 T11). */
export function supported(node) {
  if (UNSUPPORTED.has(node.type)) return false;
  if (node.type === "image" && !allowedUri(node.url)) return false;
  return (node.children ?? []).every(supported);
}

/** The page view turns wiki links into links before parsing (`wikilinks.mjs`). Each is
 * replaced by a placeholder of the same length, so source positions stay valid: the
 * placeholder's position in the original Markdown is the wiki link. */
function hideWikiLinks(markdown) {
  return replaceWikiLinks(markdown, ({ start, end }) => `[${HOLE.repeat(end - start - 4)}]()`);
}

/** The editor's text for a wiki link: as written, without backslash escapes. */
function wikiText(written) {
  return `[[${written.slice(2, -2).replace(ESCAPE, "$1")}]]`;
}

/** A placeholder link (see HOLE). */
function isHole(node) {
  return (
    node.url === "" &&
    node.children.length === 1 &&
    node.children[0].type === "text" &&
    /^\ue000+$/.test(node.children[0].value)
  );
}

/** The nodes with the mark added; a hard break takes none (the Y.Doc keeps none on it,
 * and its marks are those of the text around it, `canonical.mjs`). */
function withMark(nodes, mark) {
  return nodes.map((node) =>
    node.type === "hardBreak" ? node : { ...node, marks: [...(node.marks ?? []), mark] },
  );
}

function inline(nodes, source) {
  const out = [];
  for (const node of nodes) {
    switch (node.type) {
      case "text":
        if (node.value) out.push({ type: "text", text: node.value });
        break;
      case "inlineCode":
        if (node.value) {
          out.push({ type: "text", text: node.value, marks: [{ type: "code" }] });
        }
        break;
      case "emphasis":
        out.push(...withMark(inline(node.children, source), { type: "italic" }));
        break;
      case "strong":
        out.push(...withMark(inline(node.children, source), { type: "bold" }));
        break;
      case "delete":
        out.push(...withMark(inline(node.children, source), { type: "strike" }));
        break;
      case "link":
        if (isHole(node)) {
          const { start, end } = node.position;
          out.push({ type: "text", text: wikiText(source.slice(start.offset, end.offset)) });
          break;
        }
        out.push(
          ...withMark(inline(node.children, source), {
            type: "link",
            attrs: { href: node.url, title: node.title ?? null },
          }),
        );
        break;
      case "image":
        out.push({
          type: "image",
          attrs: { src: node.url, alt: node.alt ?? null, title: node.title ?? null },
        });
        break;
      case "break":
        out.push({ type: "hardBreak" });
        break;
      default:
        throw new Error(`unsupported inline ${node.type}`);
    }
  }
  return out;
}

const paragraph = (content) => ({ type: "paragraph", content });

function items(list, source) {
  return list.children.map((item) => {
    let content = blocks(item.children, source);
    if (content[0]?.type !== "paragraph") content = [paragraph([]), ...content];
    if (item.checked === null || item.checked === undefined) {
      return { type: "listItem", content };
    }
    return { type: "taskItem", attrs: { checked: item.checked }, content };
  });
}

/** A list; a GFM list that mixes task items and plain items becomes one list per run
 * (the editor has two kinds). */
function lists(node, source) {
  if (node.ordered) {
    const start = node.start ?? 1;
    return [{ type: "orderedList", attrs: { start }, content: items(node, source) }];
  }
  const out = [];
  for (const item of items(node, source)) {
    const type = item.type === "taskItem" ? "taskList" : "bulletList";
    if (out.at(-1)?.type === type) out.at(-1).content.push(item);
    else out.push({ type, content: [item] });
  }
  return out;
}

/** A table as wide as its widest row (review M2 T1/T10): the browser's editor makes
 * every row equally wide when it loads a table, so the parser does it first. A short
 * row gets empty cells (the page view shows them so, too); a row longer than the
 * header gets empty headings at the end, so its last cells stay over their own column
 * and visible in the page view (which hides cells beyond the header). */
function table(node, source) {
  const width = Math.max(...node.children.map((row) => row.children.length));
  const columns = Array.from({ length: width }, (_, column) => column);
  return {
    type: "table",
    content: node.children.map((row, index) => ({
      type: "tableRow",
      content: columns.map((column) => ({
        type: index === 0 ? "tableHeader" : "tableCell",
        attrs: { align: node.align?.[column] ?? null },
        content: [
          { type: "tableParagraph", content: inline(row.children[column]?.children ?? [], source) },
        ],
      })),
    })),
  };
}

function block(node, source) {
  switch (node.type) {
    case "paragraph":
      return [paragraph(inline(node.children, source))];
    case "heading":
      return [
        { type: "heading", attrs: { level: node.depth }, content: inline(node.children, source) },
      ];
    case "thematicBreak":
      return [{ type: "horizontalRule" }];
    case "blockquote": {
      const content = blocks(node.children, source);
      return [{ type: "blockquote", content: content.length ? content : [paragraph([])] }];
    }
    case "list":
      return lists(node, source);
    case "code": {
      const language = [node.lang, node.meta].filter(Boolean).join(" ") || null;
      const content = node.value ? [{ type: "text", text: node.value }] : [];
      return [{ type: "codeBlock", attrs: { language }, content }];
    }
    case "table":
      return [table(node, source)];
    default:
      throw new Error(`unsupported block ${node.type}`);
  }
}

function blocks(nodes, source) {
  return nodes.flatMap((node) => block(node, source));
}

/** A raw block: the source text of a block the editor cannot show. */
export function rawBlock(text) {
  return {
    type: "codeBlock",
    attrs: { language: RAW_MARKDOWN },
    content: text ? [{ type: "text", text }] : [],
  };
}

/**
 * The editor's document for the Markdown. Each top-level block becomes editor nodes,
 * or a raw block when it holds what the editor cannot show or when `keepRaw(index,
 * source)` says so. Returns the document and the top-level blocks' source texts.
 */
export function parseMarkdown(markdown, keepRaw = () => false) {
  const hidden = hideWikiLinks(markdown);
  const tree = fromMarkdown(hidden, {
    extensions: [gfm()],
    mdastExtensions: [gfmFromMarkdown()],
  });
  const sources = [];
  const content = [];
  tree.children.forEach((node, index) => {
    // From the start of its line: the indentation before a block is part of it.
    const { start, end } = node.position;
    const source = markdown.slice(start.offset - (start.column - 1), end.offset);
    sources.push(source);
    if (!supported(node) || keepRaw(index, source)) {
      content.push(rawBlock(source));
    } else {
      content.push(...block(node, markdown));
    }
  });
  // An empty page holds one empty paragraph, as the browser's editor shows it: built
  // into the shared document, undoing everything typed leaves that paragraph (an empty
  // shared document would stop the browser, review M2 T6).
  if (content.length === 0) content.push({ type: "paragraph" });
  return { json: { type: "doc", content }, sources };
}
