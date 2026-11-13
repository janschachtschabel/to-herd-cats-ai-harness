// The editor's extensions, one list for the browser's live editor and for the collab
// process, so both use the same schema. Plain ESM, depends only on Tiptap packages.
//
// The schema holds only what Markdown can say (review M2 S2): images are inline, as in
// Markdown; a table cell holds one line of text (`tableParagraph`: no blocks, no hard
// breaks); a heading has no hard breaks; code may carry a link or emphasis
// (`` [`a`](b) ``, `` **`a`** ``). Markdown is read and written by `parse.mjs` and
// `serialize.mjs`, not by Tiptap's Markdown support.
import { InputRule, Node } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Code from "@tiptap/extension-code";
import CodeBlock from "@tiptap/extension-code-block";
import Heading from "@tiptap/extension-heading";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import { TaskItem, TaskList } from "@tiptap/extension-list";

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

const LINE = "(text | image)*"; // inline content without hard breaks

/** The one line of text of a table cell (GFM cells hold inline content only). */
const TableParagraph = Node.create({
  name: "tableParagraph",
  content: LINE,
  parseHTML: () => [
    { tag: "p", context: "tableCell/", priority: 60 },
    { tag: "p", context: "tableHeader/", priority: 60 },
  ],
  renderHTML: () => ["p", 0],
});

// `![alt](src)` or `![alt](src "title")` just typed (Tiptap's image rule).
const TYPED_IMAGE = /(?:^|\s)(!\[(.+|:?)]\((\S+)(?:(?:\s+)["'](\S+)["'])?\))$/;

/** Images as Markdown has them: source, alt text and title; no marks (the Y.Doc keeps
 * none on an image, so a linked image could not be shared; it stays a raw block). */
const MarkdownImage = Image.extend({
  marks: "",
  // Tiptap's own rule types the closing `)` again after the image; this one does not.
  addInputRules() {
    return [
      new InputRule({
        find: TYPED_IMAGE,
        handler: ({ state, range, match }) => {
          const [whole, image, alt, src, title] = match;
          const from = range.from + whole.lastIndexOf(image);
          state.tr.replaceWith(
            from,
            range.to,
            this.type.create({ src, alt, title: title ?? null }),
          );
        },
      }),
    ];
  },
  addAttributes() {
    return {
      src: { default: null },
      alt: { default: null },
      title: { default: null },
    };
  },
});

export function extensions() {
  return [
    StarterKit.configure({
      code: false,
      heading: false,
      undoRedo: false, // the browser uses Yjs' undo
      underline: false, // no Markdown for it
      // Each browser that joins would add its own empty last paragraph to the shared
      // document; the gap cursor reaches the end without one.
      trailingNode: false,
      link: false,
      codeBlock: false,
    }),
    Code.extend({ excludes: "" }),
    Heading.extend({ content: LINE }),
    CodeBlock,
    Link.configure({ openOnClick: false, isAllowedUri: (url) => allowedUri(url) }),
    // Inline, as in Markdown: an image may stand in a sentence, a cell, a list item or a
    // heading; as a block node the browser would delete such a paragraph (review M2 S1).
    MarkdownImage.configure({ inline: true }),
    Table.configure({ resizable: false }),
    TableRow,
    TableHeader.extend({ content: "tableParagraph" }),
    TableCell.extend({ content: "tableParagraph" }),
    TableParagraph,
    TaskList,
    TaskItem.configure({ nested: true }),
  ];
}
