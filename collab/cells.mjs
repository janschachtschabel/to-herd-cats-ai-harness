// The table cell cap of live editing (review M2 U2). A table cell costs a live document
// far more than its text (a check of a table of 20,000 cells ran a check worker out of
// memory, and every cell is about a hundred bytes of Yjs state and about 1.5 KB of the
// collab process's heap while the page is open: a page of 9,606 cells held ~30 MB, and
// eight of them took the process over 512 MiB, review M4-1 P12), so a page whose tables
// hold more than MAX_TABLE_CELLS cells in all is too large for live editing (larger
// tables are edited as Markdown source). Counted
// cheaply, on this thread, before a check worker is asked: on opening from the stored
// Markdown (4413), on saving from the editor's document (not stored, "too large").
// The count is the page view's parser's: a table is as wide as its widest row.

export const MAX_TABLE_CELLS = 5_000;

const FENCE = /^(`{3,}|~{3,})/;
const DELIMITER_CELL = /^\s*:?-+:?\s*$/;
// A line that starts another block ends a table (GFM).
const OTHER_BLOCK = /^(#{1,6}(\s|$)|`{3,}|~{3,}|[-*+]\s|\d{1,9}[.)]\s|([-*_])(\s*\3){2,}\s*$)/;

/** A line without its indentation and quote markers. */
const bare = (line) => line.replace(/^[ \t>]*/, "");

/** The cells of a table line: pipes not escaped split it; outer pipes are not cells. */
function cellsOf(line) {
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (/(^|[^\\])(\\\\)*\|$/.test(text)) text = text.slice(0, -1);
  let count = 1;
  let backslashes = 0;
  for (const char of text) {
    if (char === "|" && backslashes % 2 === 0) count += 1;
    backslashes = char === "\\" ? backslashes + 1 : 0;
  }
  return count;
}

function isDelimiterRow(line) {
  if (!line.includes("|") && !/^\s*:?-+:?\s*$/.test(line)) return false;
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|")) text = text.slice(0, -1);
  return text.split("|").every((cell) => DELIMITER_CELL.test(cell));
}

/** The table cells of the Markdown, as the page view's parser would build them. */
export function markdownTableCells(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n").map(bare);
  let total = 0;
  let fence = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const opened = FENCE.exec(line);
    if (fence) {
      if (opened && opened[1][0] === fence[0] && opened[1].length >= fence.length) fence = null;
      continue;
    }
    if (opened) {
      fence = opened[1];
      continue;
    }
    const delimiter = lines[i + 1];
    if (!line.includes("|") || delimiter === undefined || OTHER_BLOCK.test(delimiter)) continue;
    if (!isDelimiterRow(delimiter)) continue;
    const width = cellsOf(line);
    if (cellsOf(delimiter) !== width) continue;
    let widest = width;
    let rows = 1;
    let j = i + 2;
    for (; j < lines.length && lines[j].trim() !== "" && !OTHER_BLOCK.test(lines[j]); j++) {
      widest = Math.max(widest, cellsOf(lines[j]));
      rows += 1;
    }
    total += widest * rows;
    i = j - 1;
  }
  return total;
}

/** The cells of a table node (editor JSON): as wide as its widest row. */
function tableCells(table) {
  const rows = table.content ?? [];
  return rows.length * Math.max(0, ...rows.map((row) => (row.content ?? []).length));
}

/** The table cells of the editor's document (JSON). */
export function jsonTableCells(node) {
  if (node?.type === "table") return tableCells(node);
  return (node?.content ?? []).reduce((sum, child) => sum + jsonTableCells(child), 0);
}

/** `{ cells, block }`: the cells of the document's tables and the top-level block
 * holding the most of them (null without tables). */
export function tableLoad(json) {
  let cells = 0;
  let block = null;
  let most = 0;
  (json?.content ?? []).forEach((child, index) => {
    const own = jsonTableCells(child);
    cells += own;
    if (own > most) [most, block] = [own, index];
  });
  return { cells, block };
}
