// Wiki links (`[[Titel]]`, a link to another page by its title) as the page view finds
// them: in the page's text as the Markdown parser reads it, never in code, HTML, link
// destinations, image descriptions or a link's own text (review M2 S2). One module for
// the page view (frontend `resolveWikiLinks`), the meaning check (`meaning.mjs`) and the
// live editor's parser (`parse.mjs`), so all three see the same links. Plain ESM; the
// browser imports it too.
import { fromMarkdown } from "mdast-util-from-markdown";
import { gfmFromMarkdown } from "mdast-util-gfm";
import { gfm } from "micromark-extension-gfm";

import { WIKI_LINK } from "./syntax.mjs";

export { WIKI_LINK };
const ESCAPE = /\\([!-/:-@[-`{-~])/g;

// GFM without its autolink transform, which splits text nodes into pieces that carry no
// source position; the parser's own autolinks (`https://…` in the source) stay.
const mdastExtensions = gfmFromMarkdown().map((extension) => {
  const { transforms, ...rest } = extension;
  void transforms;
  return rest;
});

/** The title a wiki link's inner text names: backslash escapes removed, trimmed. */
export function wikiTitle(inner) {
  return inner.replace(ESCAPE, "$1").trim();
}

function collect(node, markdown, out) {
  if (node.type === "link" || node.type === "linkReference") return;
  if (node.type === "text" && node.position) {
    const start = node.position.start.offset;
    const source = markdown.slice(start, node.position.end.offset);
    for (const match of source.matchAll(WIKI_LINK)) {
      const from = start + match.index;
      out.push({ start: from, end: from + match[0].length, title: wikiTitle(match[1]) });
    }
    return;
  }
  for (const child of node.children ?? []) collect(child, markdown, out);
}

/** The wiki links of the Markdown: `{ start, end, title }`, in order. */
export function wikiLinks(markdown) {
  const tree = fromMarkdown(markdown, { extensions: [gfm()], mdastExtensions });
  const out = [];
  collect(tree, markdown, out);
  return out;
}

/** The Markdown with each wiki link replaced by `replace({ start, end, title })`. */
export function replaceWikiLinks(markdown, replace) {
  let out = "";
  let last = 0;
  for (const link of wikiLinks(markdown)) {
    out += markdown.slice(last, link.start) + replace(link);
    last = link.end;
  }
  return out + markdown.slice(last);
}

/** A title as link text that shows exactly the title. */
export function linkText(title) {
  return title.replace(/[!-/:-@[-`{-~]/g, "\\$&");
}
