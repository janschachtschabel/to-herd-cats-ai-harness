// What a page's Markdown means to the page view, independent of how it is written
// (review M2 R1). The page view renders with react-markdown + remark-gfm, whose parser
// is micromark with the GFM extensions; the same parser builds the syntax tree here.
// Two Markdown texts mean the same when their trees are equal after dropping what does
// not change the rendered page: source positions, runs of whitespace inside text,
// tight/loose lists. Wiki links (`[[Titel]]`) are resolved on the source text by the
// page view (frontend/src/features/wiki/markdown.ts `resolveWikiLinks`), so they are
// turned into links with the raw title first, the way the page view does it.
import { fromMarkdown } from "mdast-util-from-markdown";
import { gfmFromMarkdown } from "mdast-util-gfm";
import { gfm } from "micromark-extension-gfm";

import { WIKI_LINK, outsideCode } from "./syntax.mjs";

const IGNORED = new Set(["position", "spread"]);

/** `[[Titel]]` → `[Titel](wiki:Titel)`, outside code (as the page view does). */
export function markWikiLinks(markdown) {
  return outsideCode(markdown, (text) =>
    text.replace(WIKI_LINK, (_, raw) => {
      const title = raw.trim();
      return `[${title}](wiki:${encodeURIComponent(title)})`;
    }),
  );
}

function normalize(node) {
  const out = {};
  for (const [key, value] of Object.entries(node)) {
    if (IGNORED.has(key) || value === null || value === undefined) continue;
    if (key === "children") out.children = normalizeChildren(value);
    else if (key === "value" && node.type === "text") out.value = value.replace(/[ \t\r\n]+/g, " ");
    else if (key === "value" && node.type === "inlineCode") out.value = value.replace(/\n/g, " ");
    else if (key === "value" && (node.type === "html" || node.type === "code")) {
      out.value = value.replace(/\s+$/, "");
    } else out[key] = value;
  }
  return out;
}

function normalizeChildren(children) {
  const out = [];
  for (const child of children.map(normalize)) {
    const last = out.at(-1);
    if (child.type === "text" && last?.type === "text") {
      last.value = `${last.value}${child.value}`.replace(/ +/g, " ");
    } else out.push(child);
  }
  return out;
}

/** The normalised syntax tree of the Markdown, as the page view would read it. */
export function meaningOf(markdown) {
  const tree = fromMarkdown(markWikiLinks(markdown), {
    extensions: [gfm()],
    mdastExtensions: [gfmFromMarkdown()],
  });
  return normalize(tree);
}

/** The first place where two trees differ (a path like `children.2.children.0.value`),
 * or null when they are equal. */
export function difference(a, b, path = "") {
  if (a === b) return null;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return path;
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    const found = difference(a[key], b[key], path ? `${path}.${key}` : key);
    if (found !== null) return found;
  }
  return null;
}

/** Whether two Markdown texts render the same page. */
export function sameMeaning(a, b) {
  return difference(meaningOf(a), meaningOf(b)) === null;
}
