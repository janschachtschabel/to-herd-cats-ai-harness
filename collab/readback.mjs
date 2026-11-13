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
import { editorProblem, liveDocument, normalized } from "./markdown.mjs";
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

/** `{ ok: true, markdown }`, or `{ ok: false, markdown, problem, kind, block, through }`
 * when the Markdown must not be stored for this document. `kind`: "structure" (the
 * editor cannot hold the document), "reopen" (the live editor would not open the
 * Markdown unchanged) or "markdown" (it reads back as something else). `block`: the
 * index of the first top-level block that fails on its own; when none does, of the
 * first of two neighbours that fail together (`through`: the second; review M2 U1);
 * null when neither is found. */
export function readBack(json) {
  const result = check(json);
  if (result.ok) return result;
  return { ...result, ...firstFailing(json) };
}

const fails = (...blocks) => !check({ type: "doc", content: blocks }).ok;

/** Where the check fails: the first top-level block that fails alone, else the first
 * pair of neighbours that fails together. Only run for a state that failed, so a save
 * that passes costs nothing more. */
function firstFailing(json) {
  const blocks = json?.content ?? [];
  if (blocks.length < 2) return { block: blocks.length === 1 ? 0 : null, through: null };
  const alone = blocks.findIndex((block) => fails(block));
  if (alone !== -1) return { block: alone, through: null };
  const pair = blocks.findIndex(
    (block, index) => index + 1 < blocks.length && fails(block, blocks[index + 1]),
  );
  return pair === -1 ? { block: null, through: null } : { block: pair, through: pair + 1 };
}

function check(json) {
  const problem = editorProblem(json);
  if (problem !== null) return { ok: false, markdown: null, problem, kind: "structure" };
  const markdown = jsonToMarkdown(json);
  const opened = liveDocument(markdown);
  if (!opened.safe) {
    return { ok: false, markdown, problem: "the live editor would refuse it", kind: "reopen" };
  }
  const sources = [];
  const expected = splitRaw(json, sources);
  // Without raw blocks, the live editor's own reading (nothing kept raw) is the one.
  const back =
    sources.length === 0 && opened.plain && markdown === normalized(markdown)
      ? opened.json
      : parseMarkdown(markdown, (_, source) => {
          const index = sources.indexOf(source);
          if (index === -1) return false;
          sources.splice(index, 1);
          return true;
        }).json;
  const where = difference(withAutolinks(canonical(expected)), withAutolinks(canonical(back)));
  if (where !== null) {
    return { ok: false, markdown, problem: `reads back differently at ${where}`, kind: "markdown" };
  }
  return { ok: true, markdown };
}
