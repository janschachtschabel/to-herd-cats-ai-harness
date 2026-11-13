// The editor's extensions, one list for the browser's live editor and for the collab
// process (Markdown conversion), so both use the same schema. Plain ESM, depends
// only on Tiptap packages.
import StarterKit from "@tiptap/starter-kit";
import CodeBlock from "@tiptap/extension-code-block";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { TaskItem, TaskList } from "@tiptap/extension-list";

export const RAW_MARKDOWN = "raw-markdown";

const LINK_PROTOCOLS = ["http", "https", "mailto"];

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
      link: { openOnClick: false, protocols: LINK_PROTOCOLS },
    }),
    SafeCodeBlock,
    Image,
    TableKit.configure({ table: { resizable: false } }),
    TaskList,
    TaskItem.configure({ nested: true }),
  ];
}
