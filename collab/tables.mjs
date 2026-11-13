// Tables in the live editor as GFM has them (review M2 T3, T4, T8): rows of cells
// holding one line of text each, no merged cells, one alignment per column.
//
// - A cell holds one `tableParagraph` (inline content, no hard breaks); Enter,
//   Shift+Enter and Mod+Enter in it do nothing (Shift+Enter fell through to splitting
//   the table, T8). Pasted lines, paragraphs, rows and tabs are joined into the cell's
//   line with single spaces (U4).
// - A merged cell has no Markdown: `colspan` and `rowspan` stay 1 (prosemirror-tables
//   needs the attributes; HTML cannot set them), and a pasted table with merged cells is
//   flattened first: each merged cell becomes its cells, the content in the first (T4).
// - A column has one alignment, its header cell's: a row added with Tab takes it (T3).
import { Extension, Node } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";

const LINE = "(text | image)*"; // inline content without hard breaks

const nothing = ({ editor }) => editor.state.selection.$from.parent.type.name === "tableParagraph";

/** The one line of text of a table cell (GFM cells hold inline content only). */
const TableParagraph = Node.create({
  name: "tableParagraph",
  content: LINE,
  // Before the hard break's and the list's keys: in a cell these keys do nothing.
  priority: 200,
  parseHTML: () => [
    { tag: "p", context: "tableCell/", priority: 60 },
    { tag: "p", context: "tableHeader/", priority: 60 },
  ],
  renderHTML: () => ["p", 0],
  addKeyboardShortcuts: () => ({
    Enter: nothing,
    "Shift-Enter": nothing,
    "Mod-Enter": nothing,
  }),
});

/** Cells that are never merged: the spans are always 1, whatever HTML says. */
function oneByOne(base) {
  return base.extend({
    content: "tableParagraph",
    addAttributes() {
      return {
        ...this.parent?.(),
        colspan: { default: 1, parseHTML: () => 1 },
        rowspan: { default: 1, parseHTML: () => 1 },
        colwidth: { default: null, parseHTML: () => null },
      };
    },
  });
}

/** The table elements of the HTML with every merged cell split into its cells (the
 * content stays in the first). Needs a DOM (`ownerDocument`). */
export function flattenTableSpans(root) {
  for (const table of root.querySelectorAll("table")) {
    const rows = [...table.rows];
    const grid = rows.map(() => []);
    rows.forEach((row, r) => {
      let column = 0;
      for (const cell of [...row.cells]) {
        while (grid[r][column]) column += 1;
        const across = Math.max(1, Number(cell.getAttribute("colspan")) || 1);
        const down = Math.max(1, Number(cell.getAttribute("rowspan")) || 1);
        for (let dr = 0; dr < down && r + dr < rows.length; dr += 1) {
          for (let dc = 0; dc < across; dc += 1) {
            grid[r + dr][column + dc] = { cell, first: dr === 0 && dc === 0 };
          }
        }
        column += across;
      }
    });
    rows.forEach((row, r) => {
      const cells = Array.from(grid[r], (slot) => {
        if (slot?.first) {
          slot.cell.removeAttribute("colspan");
          slot.cell.removeAttribute("rowspan");
          return slot.cell;
        }
        const empty = (slot?.cell ?? row).ownerDocument.createElement(
          slot?.cell.tagName.toLowerCase() ?? "td",
        );
        return empty;
      });
      row.replaceChildren(...cells);
    });
  }
  return root;
}

const alignKey = new PluginKey("herdColumnAlignment");

/** Every cell of a column takes the alignment of the column's header cell. */
function columnAlignment() {
  return new Plugin({
    key: alignKey,
    appendTransaction(transactions, _old, state) {
      if (!transactions.some((transaction) => transaction.docChanged)) return undefined;
      let tr = null;
      state.doc.descendants((node, pos) => {
        if (node.type.name !== "table") return !node.isTextblock;
        const header = node.firstChild;
        node.forEach((row, rowOffset, index) => {
          if (index === 0) return;
          row.forEach((cell, cellOffset, column) => {
            const align = header?.maybeChild(column)?.attrs.align ?? null;
            if (cell.attrs.align === align) return;
            tr ??= state.tr;
            tr.setNodeAttribute(pos + 1 + rowOffset + 1 + cellOffset, "align", align);
          });
        });
        return false;
      });
      return tr ?? undefined;
    },
  });
}

const SPACE = /[\t\n\r]+/g;

/** The inline content of a pasted slice as one line (review M2 U4): its text blocks
 * (lines, paragraphs, a table's cells) joined with a single space; line breaks and tabs
 * become spaces; marks stay. */
function oneLine(slice, schema) {
  const out = [];
  const space = () => {
    const last = out.at(-1);
    if (last && !(last.isText && last.text.endsWith(" "))) out.push(schema.text(" "));
  };
  const take = (node) => {
    if (node.isText) out.push(schema.text(node.text.replace(SPACE, " "), node.marks));
    else if (node.type.name === "image") out.push(node);
    else space(); // a hard break
  };
  let first = true;
  slice.content.descendants((node) => {
    if (node.isInline) {
      take(node);
      return false;
    }
    if (!node.isTextblock) return true;
    if (!first) space();
    first = false;
    node.forEach(take);
    return false;
  });
  return out.filter((node) => !node.isText || node.text !== "");
}

/** Paste into a table cell (one line of text): everything pasted becomes that line, so
 * a table is never split (review M2 U4). */
function pasteIntoCell(view, _event, slice) {
  const { $from, $to } = view.state.selection;
  if ($from.parent.type.name !== "tableParagraph" || !$from.sameParent($to)) return false;
  const nodes = oneLine(slice, view.state.schema);
  view.dispatch(view.state.tr.replaceWith($from.pos, $to.pos, nodes).scrollIntoView());
  return true;
}

/** Pasted HTML: tables with merged cells flattened (only in a browser); anything pasted
 * into a cell joined into its line. */
const PastedTables = Extension.create({
  name: "pastedTables",
  addProseMirrorPlugins: () => [
    new Plugin({
      props: {
        handlePaste: pasteIntoCell,
        transformPastedHTML(html) {
          if (!/\b(colspan|rowspan)\b/i.test(html) || typeof DOMParser === "undefined") {
            return html;
          }
          const document = new DOMParser().parseFromString(html, "text/html");
          return flattenTableSpans(document.body).innerHTML;
        },
      },
    }),
  ],
});

const MarkdownTable = Table.extend({
  addProseMirrorPlugins() {
    return [...(this.parent?.() ?? []), columnAlignment()];
  },
});

export function tableExtensions() {
  return [
    MarkdownTable.configure({ resizable: false }),
    TableRow,
    oneByOne(TableHeader),
    oneByOne(TableCell),
    TableParagraph,
    PastedTables,
  ];
}
