// The editor's document as Markdown (review M2 S2, S3, S5). The document is first put
// into its canonical form (`canonical.mjs`: what the editor shows, without what
// Markdown cannot say), then written block by block so that the page view's parser
// reads it back as the same canonical form; a save checks exactly that
// (`readback.mjs`). Plain ESM; the browser's live editor uses it too (copying text
// that could not be saved).
import { canonical } from "./canonical.mjs";
import { writeInline } from "./inline.mjs";
import { RAW_MARKDOWN } from "./schema.mjs";
import { escapeBlockStart } from "./syntax.mjs";

const LIST_FAMILY = { bulletList: "bullet", taskList: "bullet", orderedList: "ordered" };
const MARKERS = { bullet: ["-", "*"], ordered: [".", ")"] };
const ALIGN = { left: ":--", right: "--:", center: ":-:" };

function prefixLines(text, first, rest) {
  return text
    .split("\n")
    .map((line, index) => {
      if (index === 0) return line ? `${first}${line}` : first.trimEnd();
      return line ? `${rest}${line}` : "";
    })
    .join("\n");
}

function paragraph(block) {
  return writeInline(block.inline).split("\n").map(escapeBlockStart).join("\n");
}

function heading(block) {
  // A `#` at the end would be read as a closing sequence.
  const text = writeInline(block.inline).replace(/#$/, "\\#");
  const marks = "#".repeat(block.level);
  return text ? `${marks} ${text}` : marks;
}

function codeBlock(block) {
  if (block.language === RAW_MARKDOWN) return block.text;
  // A fence longer than any run of its character in the code, so the code cannot end
  // it; tildes when the info string holds a backtick (not allowed after backticks).
  const char = block.language.includes("`") ? "~" : "`";
  const runs = block.text.match(char === "`" ? /`+/g : /~+/g) ?? [];
  const fence = char.repeat(Math.max(3, ...runs.map((run) => run.length + 1)));
  return `${fence}${block.language}\n${block.text}${block.text ? "\n" : ""}${fence}`;
}

function table(block) {
  const rows = block.content.map(
    (row) =>
      `| ${row.content
        .map((cell) =>
          cell.content.map((child) => writeInline(child.inline, { table: true })).join(" "),
        )
        .join(" | ")} |`,
  );
  const header = block.content[0]?.content ?? [];
  const delimiter = `| ${header.map((cell) => ALIGN[cell.align] ?? "---").join(" | ")} |`;
  return [rows[0], delimiter, ...rows.slice(1)].join("\n");
}

const MAX_NUMBER = 999999999; // an ordered list item's number has at most nine digits

/** Whether `next` may follow `previous` in a list item on the next line (no blank line
 * between them, so the list stays tight): a nested list, a fenced code block, a heading
 * or a quote right after a line of text or code; anything else needs a blank line. */
function tightPair(previous, next) {
  if (!["paragraph", "heading", "codeBlock"].includes(previous.type)) return false;
  if (previous.type === "codeBlock" && previous.language === RAW_MARKDOWN) return false;
  if (next.type === "codeBlock") return next.language !== RAW_MARKDOWN;
  if (next.type === "heading") return true;
  if (!LIST_FAMILY[next.type] || !next.content[0]?.content.length) return false;
  // Only a bullet list or one starting at 1 can interrupt a paragraph.
  return previous.type !== "paragraph" || next.type !== "orderedList" || next.start === 1;
}

function list(block, variant) {
  const family = LIST_FAMILY[block.type];
  const marker = MARKERS[family][variant];
  const tight = block.content.every((item) =>
    item.content.every((child, i) => i === 0 || tightPair(item.content[i - 1], child)),
  );
  const start = block.start ?? 1;
  const items = block.content.map((item, index) => {
    let first;
    if (family === "ordered") first = `${Math.min(start + index, MAX_NUMBER)}${marker} `;
    else if (item.type === "taskItem") first = `${marker} [${item.checked ? "x" : " "}] `;
    else first = `${marker} `;
    const indent = " ".repeat(family === "ordered" ? first.length : 2);
    let text = blocks(item.content, tight ? "\n" : "\n\n");
    // `- ---` would be a rule of its own, not a list item holding one.
    if (item.content[0]?.type === "horizontalRule") text = `___${text.slice(3)}`;
    return prefixLines(text, first, indent);
  });
  return items.join(tight ? "\n" : "\n\n");
}

function blockText(block, variant) {
  switch (block.type) {
    case "paragraph":
      return paragraph(block);
    case "heading":
      return heading(block);
    case "codeBlock":
      return codeBlock(block);
    case "horizontalRule":
      return "---";
    case "blockquote":
      return prefixLines(blocks(block.content), "> ", "> ").replace(/^$/gm, ">");
    case "bulletList":
    case "taskList":
    case "orderedList":
      return list(block, variant);
    case "table":
      return table(block);
    default:
      return "";
  }
}

/** Blocks separated by blank lines (or `separator`); a list right after a list of the
 * same family takes the other marker, so the two stay two lists. */
function blocks(content, separator = "\n\n") {
  const out = [];
  let previousFamily = null;
  let variant = 0;
  for (const block of content) {
    const family = LIST_FAMILY[block.type] ?? null;
    variant = family && family === previousFamily ? 1 - variant : 0;
    previousFamily = family;
    out.push(blockText(block, variant));
  }
  return out.join(separator);
}

/** The canonical form (`canonical.mjs`) as Markdown. */
export function writeMarkdown(form) {
  return blocks(form.content ?? []);
}

/** The editor's document (JSON) as Markdown. */
export function jsonToMarkdown(json) {
  return writeMarkdown(canonical(json));
}
