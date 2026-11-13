// The editor's extensions, one list for the browser's live editor and for the collab
// process (Markdown conversion), so both use the same schema. Plain ESM, depends
// only on Tiptap packages.
import StarterKit from "@tiptap/starter-kit";
import CodeBlock from "@tiptap/extension-code-block";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Paragraph from "@tiptap/extension-paragraph";
import { Table, TableKit } from "@tiptap/extension-table";
import { ListItem, OrderedList, TaskItem, TaskList } from "@tiptap/extension-list";
import { altText, destination, escapeBlockStarts, keepWikiLinks, title } from "./syntax.mjs";

export { keepWikiLinks };

export const RAW_MARKDOWN = "raw-markdown";

const LINK_PROTOCOLS = new Set(["http", "https", "mailto"]);

/** Links only to http, https, mailto and relative targets (as the page view renders). */
export function allowedUri(url) {
  const value = String(url).trim();
  const colon = value.indexOf(":");
  const stop = value.search(/[/?#]/);
  if (colon === -1 || (stop !== -1 && stop < colon)) return true;
  return LINK_PROTOCOLS.has(value.slice(0, colon).toLowerCase());
}

function text(node) {
  return (node.content ?? []).map((child) => child.text ?? "").join("");
}

/** A fence longer than any run of backticks in the code, so the code cannot end it. */
function fenceFor(code) {
  const longest = Math.max(0, ...(code.match(/`+/g) ?? []).map((run) => run.length));
  return "`".repeat(Math.max(3, longest + 1));
}

/** Code blocks; a `raw-markdown` block is Markdown the editor cannot show, written
 * back exactly as it came. */
const SafeCodeBlock = CodeBlock.extend({
  renderMarkdown(node) {
    const code = text(node);
    const language = node.attrs?.language || "";
    if (language === RAW_MARKDOWN) return code;
    const fence = fenceFor(code);
    return `${fence}${language}\n${code}\n${fence}`;
  },
});

const NBSP = "\u00a0";
const EMPTY_PARAGRAPH = "&nbsp;";

/** Paragraphs whose text cannot turn into other blocks when read again, and a
 * paragraph of a single `&nbsp;` (a deliberate blank paragraph) kept as one. */
const SafeParagraph = Paragraph.extend({
  parseMarkdown(token, helpers) {
    const tokens = token.tokens ?? [];
    if (tokens.length === 1 && tokens[0].type === "image") return helpers.parseChildren(tokens);
    return helpers.createNode("paragraph", undefined, helpers.parseInline(tokens));
  },
  renderMarkdown(node, h, ctx) {
    const content = node.content ?? [];
    if (content.length === 0) {
      const previous = ctx?.previousNode;
      const afterEmpty = previous?.type === "paragraph" && !(previous.content ?? []).length;
      return afterEmpty ? EMPTY_PARAGRAPH : "";
    }
    if (content.length === 1 && content[0].text === NBSP && !content[0].marks?.length) {
      return EMPTY_PARAGRAPH;
    }
    return escapeBlockStarts(h.renderChildren(content));
  },
});

/** Link destinations and titles written so they read back as the same link. */
const SafeLink = Link.extend({
  renderMarkdown(node, h) {
    const href = destination(node.attrs?.href ?? "");
    const text = h.renderChildren(node);
    return node.attrs?.title
      ? `[${text}](${href} ${title(node.attrs.title)})`
      : `[${text}](${href})`;
  },
});

const SafeImage = Image.extend({
  renderMarkdown(node) {
    const src = destination(node.attrs?.src ?? "");
    const alt = altText(node.attrs?.alt);
    return node.attrs?.title ? `![${alt}](${src} ${title(node.attrs.title)})` : `![${alt}](${src})`;
  },
});

// Tiptap's own ordered-list tokenizer misreads content indented by three spaces
// (`1. Text` followed by a code block); marked's list tokens are read instead, item by
// item like a bullet list's.
const MarkedOrderedList = OrderedList.extend({
  markdownTokenizer: null,
  parseMarkdown(token, helpers) {
    if (token.type !== "list" || !token.ordered) return [];
    const content = token.items ? helpers.parseChildren(token.items) : [];
    const start = typeof token.start === "number" ? token.start : 1;
    return { type: "orderedList", ...(start !== 1 && { attrs: { start } }), content };
  },
});

// The table serializer surrounds a table with blank lines of its own, which the next
// conversion reads as empty paragraphs: every live save would add blank lines.
const TightTable = Table.extend({
  renderMarkdown(node, h) {
    return this.parent(node, h).replace(/^\n+|\n+$/g, "");
  },
});

// Text after a nested block in a list item (`1. a`, a code block, then more text)
// comes as a bare text token whose inline formatting Tiptap would drop: read it as
// the paragraph it is.
const BlockTextListItem = ListItem.extend({
  parseMarkdown(token, helpers) {
    const tokens = (token.tokens ?? []).map((child) =>
      child.type === "text" && child.tokens ? { ...child, type: "paragraph" } : child,
    );
    return this.parent({ ...token, tokens }, helpers);
  },
});

export function extensions() {
  return [
    StarterKit.configure({
      codeBlock: false,
      undoRedo: false, // the browser uses Yjs' undo
      underline: false, // no Markdown for it
      // Each browser that joins would add its own empty last paragraph to the shared
      // document (saved as `&nbsp;`); the gap cursor reaches the end without one.
      trailingNode: false,
      paragraph: false,
      link: false,
      orderedList: false,
      listItem: false,
    }),
    BlockTextListItem,
    SafeParagraph,
    SafeLink.configure({ openOnClick: false, isAllowedUri: (url) => allowedUri(url) }),
    MarkedOrderedList,
    SafeCodeBlock,
    SafeImage,
    TightTable.configure({ resizable: false }),
    TableKit.configure({ table: false }),
    TaskList,
    TaskItem.configure({ nested: true }),
  ];
}
