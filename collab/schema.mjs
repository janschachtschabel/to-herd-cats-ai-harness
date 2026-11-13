// The editor's extensions, one list for the browser's live editor and for the collab
// process, so both use the same schema. Plain ESM, depends only on Tiptap packages.
//
// The schema holds only what Markdown can say (review M2 S2): images are inline, as in
// Markdown; tables as GFM has them (`tables.mjs`: a cell holds one line of text, no
// merged cells, one alignment per column); a heading has no hard breaks; code may carry a link or emphasis
// (`` [`a`](b) ``, `` **`a`** ``). Markdown is read and written by `parse.mjs` and
// `serialize.mjs`, not by Tiptap's Markdown support.
import { InputRule } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { ySyncPluginKey } from "@tiptap/y-tiptap";
import StarterKit from "@tiptap/starter-kit";
import Code from "@tiptap/extension-code";
import CodeBlock from "@tiptap/extension-code-block";
import Heading from "@tiptap/extension-heading";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { tableExtensions } from "./tables.mjs";

export const RAW_MARKDOWN = "raw-markdown";
// The Y.Doc binding's plugin key: every transaction the binding makes carries its meta.
export const SYNC_META = ySyncPluginKey;

const LINK_PROTOCOLS = new Set(["http", "https", "mailto"]);

/** Links and images only to http, https, mailto and relative targets (as the page view
 * renders, `safeUrl` in the frontend). */
export function allowedUri(url) {
  const value = String(url).trim();
  const colon = value.indexOf(":");
  const stop = value.search(/[/?#]/);
  if (colon === -1 || (stop !== -1 && stop < colon)) return true;
  return LINK_PROTOCOLS.has(value.slice(0, colon).toLowerCase());
}

const LINE = "(text | image)*"; // inline content without hard breaks

// `![alt](src)` or `![alt](src "title")` just typed (Tiptap's image rule).
const TYPED_IMAGE = /(?:^|\s)(!\[(.+|:?)]\((\S+)(?:(?:\s+)["'](\S+)["'])?\))$/;

/** Images as Markdown has them: source, alt text and title; no marks (the Y.Doc keeps
 * none on an image, so a linked image could not be shared; it stays a raw block). An
 * image whose source the page view does not show (`blob:`, `file:`, `data:`, ...) is
 * not taken in, pasted or typed (review M2 T11). */
const MarkdownImage = Image.extend({
  marks: "",
  parseHTML() {
    return [
      {
        tag: "img[src]",
        getAttrs: (element) => (allowedUri(element.getAttribute("src") ?? "") ? null : false),
      },
    ];
  },
  // Tiptap's own rule types the closing `)` again after the image; this one does not.
  addInputRules() {
    return [
      new InputRule({
        find: TYPED_IMAGE,
        handler: ({ state, range, match }) => {
          const [whole, image, alt, src, title] = match;
          if (!allowedUri(src)) return null;
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

/** Tiptap's autolink acts on any change, a document being loaded and other people's
 * changes included (review M2 T2: `# README.md` became a link on opening). Here it acts
 * only on the person's own changes; the Y.Doc binding marks every change it makes. */
function ownChangesOnly(plugin) {
  const append = plugin.spec.appendTransaction;
  if (!plugin.key.startsWith("autolink$") || !append) return plugin;
  return new Plugin({
    ...plugin.spec,
    appendTransaction: (transactions, oldState, newState) =>
      transactions.some((transaction) => transaction.getMeta(SYNC_META) !== undefined)
        ? undefined
        : append(transactions, oldState, newState),
  });
}

const MarkdownLink = Link.extend({
  addProseMirrorPlugins() {
    return this.parent().map(ownChangesOnly);
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
    MarkdownLink.configure({ openOnClick: false, isAllowedUri: (url) => allowedUri(url) }),
    // Inline, as in Markdown: an image may stand in a sentence, a cell, a list item or a
    // heading; as a block node the browser would delete such a paragraph (review M2 S1).
    MarkdownImage.configure({ inline: true }),
    ...tableExtensions(),
    TaskList,
    TaskItem.configure({ nested: true }),
  ];
}
