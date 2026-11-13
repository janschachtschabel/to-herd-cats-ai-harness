// Bare addresses as the page view shows them (review M2 S2): GFM turns `https://…`,
// `www.…` and e-mail addresses in text into links, after parsing and whatever their
// escapes, so Markdown has no way to keep them plain text. The canonical form
// (`canonical.mjs`) therefore links them the way the page view's parser does, with the
// same code (mdast-util-gfm-autolink-literal), text node by text node. Wiki links
// (`[[…]]`) are links of their own for the page view and stay untouched.
import { gfmAutolinkLiteralFromMarkdown } from "mdast-util-gfm-autolink-literal";
import { retidy } from "./canonical.mjs";
import { WIKI_LINK, linkKey } from "./syntax.mjs";

const [transform] = gfmAutolinkLiteralFromMarkdown().transforms;
const CANDIDATE = /[@:.]/; // nothing to find without one of these

/** The text split into pieces, each `{ text, href }` (href null for plain text). */
function linked(text) {
  if (!CANDIDATE.test(text)) return [{ text, href: null }];
  const paragraph = { type: "paragraph", children: [{ type: "text", value: text }] };
  transform({ type: "root", children: [paragraph] });
  return paragraph.children.map((node) =>
    node.type === "link"
      ? { text: node.children.map((child) => child.value).join(""), href: node.url }
      : { text: node.value, href: null },
  );
}

/** Canonical runs with the page view's autolinks added to plain text runs. */
export function autolinks(runs) {
  const out = [];
  for (const run of runs) {
    const plain =
      run.t === "text" && !run.marks.some((key) => key === "code" || key.startsWith("link"));
    if (!plain) {
      out.push(run);
      continue;
    }
    let last = 0;
    const pieces = [];
    for (const match of run.text.matchAll(WIKI_LINK)) {
      pieces.push(...linked(run.text.slice(last, match.index)), { text: match[0], href: null });
      last = match.index + match[0].length;
    }
    pieces.push(...linked(run.text.slice(last)));
    for (const piece of pieces) {
      if (!piece.text) continue;
      const marks = piece.href ? [...run.marks, linkKey({ href: piece.href })].sort() : run.marks;
      const previous = out.at(-1);
      if (previous?.t === "text" && previous.marks.join("\n") === marks.join("\n")) {
        previous.text += piece.text;
      } else out.push({ t: "text", text: piece.text, marks });
    }
  }
  return out;
}

/** The canonical form (`canonical.mjs`) with the page view's autolinks in every text
 * block. */
export function withAutolinks(form) {
  if (Array.isArray(form)) return form.map(withAutolinks);
  if (!form || typeof form !== "object") return form;
  const out = {};
  for (const [key, value] of Object.entries(form)) {
    out[key] = key === "inline" ? retidy(autolinks(value)) : withAutolinks(value);
  }
  return out;
}
