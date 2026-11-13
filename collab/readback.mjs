// The check before every live save (review M2 S2, S3): the Markdown written for the
// editor's document must
// (1) read back, with the page view's parser, as that same document (canonical forms
//     equal: what the people in the editor see is what the page shows), and
// (2) open again in the live editor (`liveDocument` calls it safe), so a save can
//     never produce a page the live editor then refuses.
// Raw blocks (Markdown the editor shows as source) count as their source: each of their
// top-level blocks must come back as a raw block with the same text.
import { withAutolinks } from "./autolink.mjs";
import { canonical } from "./canonical.mjs";
import { editorProblem, liveDocument } from "./markdown.mjs";
import { difference } from "./meaning.mjs";
import { parseMarkdown, rawBlock } from "./parse.mjs";
import { RAW_MARKDOWN } from "./schema.mjs";
import { jsonToMarkdown } from "./serialize.mjs";

const CONTAINERS = new Set(["doc", "blockquote", "listItem", "taskItem"]);
const isRaw = (node) => node.type === "codeBlock" && node.attrs?.language === RAW_MARKDOWN;
const rawText = (node) => (node.content ?? []).map((child) => child.text ?? "").join("");

/** The document with each raw block split into its top-level blocks (as raw blocks),
 * and the source texts of those blocks. */
function splitRaw(node, sources) {
  if (!CONTAINERS.has(node.type)) return node;
  const content = (node.content ?? []).flatMap((child) => {
    if (!isRaw(child)) return [splitRaw(child, sources)];
    const parts = parseMarkdown(rawText(child), () => true).sources;
    sources.push(...parts);
    return parts.map(rawBlock);
  });
  return { ...node, content };
}

/** `{ ok: true, markdown }`, or `{ ok: false, markdown, problem }` when the Markdown
 * must not be stored for this document. */
export function readBack(json) {
  const problem = editorProblem(json);
  if (problem !== null) return { ok: false, markdown: null, problem };
  const markdown = jsonToMarkdown(json);
  if (!liveDocument(markdown).safe) {
    return { ok: false, markdown, problem: "the live editor would refuse it" };
  }
  const sources = [];
  const expected = splitRaw(json, sources);
  const back = parseMarkdown(markdown, (_, source) => {
    const index = sources.indexOf(source);
    if (index === -1) return false;
    sources.splice(index, 1);
    return true;
  }).json;
  const where = difference(withAutolinks(canonical(expected)), withAutolinks(canonical(back)));
  if (where !== null) return { ok: false, markdown, problem: `reads back differently at ${where}` };
  return { ok: true, markdown };
}
