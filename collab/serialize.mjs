// The editor's document as Markdown (review M2 S2, S3, S5). The document is first put
// into its canonical form (`canonical.mjs`: what the editor shows, without what
// Markdown cannot say), then written block by block so that the page view's parser
// reads it back as the same canonical form; a save checks exactly that
// (`readback.mjs`). Plain ESM; the browser's live editor uses it too (copying text
// that could not be saved).
import { canonical } from "./canonical.mjs";
import { writeInline } from "./inline.mjs";
import { listEnds } from "./parse.mjs";
import { RAW_MARKDOWN } from "./schema.mjs";
import { escapeBlockStart } from "./syntax.mjs";

const LIST_FAMILY = { bulletList: "bullet", taskList: "bullet", orderedList: "ordered" };
const MARKERS = { bullet: ["-", "*", "+"], ordered: [".", ")"] };
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
  if (!LIST_FAMILY[next.type]) return false;
  return previous.type !== "paragraph" ? next.content[0]?.content.length > 0 : interrupts(next);
}

/** Whether a list may start on the line right after a line of text: its first item
 * holds something, a bullet list or one starting at 1, and so is every list that starts
 * on that same line (`- 1. a`: each of them would interrupt the text). */
function interrupts(list) {
  const first = list.content[0]?.content ?? [];
  if (first.length === 0) return false;
  if (list.type === "orderedList" && (list.start ?? 1) !== 1) return false;
  return !LIST_FAMILY[first[0].type] || interrupts(first[0]);
}

function list(block, marker) {
  const family = LIST_FAMILY[block.type];
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

function blockText(block, marker) {
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
      return list(block, marker);
    case "table":
      return table(block);
    default:
      return "";
  }
}

const isRaw = (block) => block?.type === "codeBlock" && block.language === RAW_MARKDOWN;

/** The list a block ends (`last`) or starts (`first`) with as Markdown, or null: a
 * raw block's from its source. An editor list's own marker is chosen when it is
 * written. */
function rawList(block, end) {
  return isRaw(block) && block.text ? listEnds(block.text)[end] : null;
}

/** Blocks separated by blank lines (or `separator`). A list takes the first marker of
 * its family that the list right before it and a raw block's list right after it do
 * not use, so Markdown reads them as separate lists (review M2 U1: a raw block's list
 * counts too). */
function blocks(content, separator = "\n\n") {
  const out = [];
  let previous = null; // the list the block before ended with: { family, marker }
  content.forEach((block, index) => {
    const family = LIST_FAMILY[block.type];
    if (!family) {
      out.push(blockText(block));
      previous = rawList(block, "last");
      return;
    }
    const taken = [previous, rawList(content[index + 1], "first")]
      .filter((end) => end?.family === family)
      .map((end) => end.marker);
    const marker = MARKERS[family].find((each) => !taken.includes(each)) ?? MARKERS[family][0];
    out.push(blockText(block, marker));
    previous = { family, marker };
  });
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
