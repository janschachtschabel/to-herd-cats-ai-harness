// The editor's extensions, one list for the browser's live editor and for the collab
// process (Markdown conversion), so both use the same schema. Plain ESM, depends
// only on Tiptap packages.
import StarterKit from "@tiptap/starter-kit";
import CodeBlock from "@tiptap/extension-code-block";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
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

export function extensions() {
  return [
    StarterKit.configure({
      codeBlock: false,
      undoRedo: false, // the browser uses Yjs' undo
      underline: false, // no Markdown for it
      // Each browser that joins would add its own empty last paragraph to the shared
      // document (saved as `&nbsp;`); the gap cursor reaches the end without one.
      trailingNode: false,
      link: { openOnClick: false, isAllowedUri: (url) => allowedUri(url) },
    }),
    SafeCodeBlock,
    Image,
    TableKit.configure({ table: { resizable: false } }),
    TaskList,
    TaskItem.configure({ nested: true }),
  ];
}

const ESCAPED_WIKI_LINK = /\\\[\\\[([^\n]+?)\\\]\\\]/g; // `\[\[Titel\]\]`
const FENCE = /^\s*(```|~~~)/;

/** The serializer escapes brackets, which would turn `[[Titel]]` (a link to another
 * page, resolved by the browser) into literal text: wiki links are written back as
 * they came, outside fenced code. */
export function keepWikiLinks(markdown) {
  let inFence = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (FENCE.test(line)) inFence = !inFence;
      else if (!inFence) return line.replace(ESCAPED_WIKI_LINK, "[[$1]]");
      return line;
    })
    .join("\n");
}
