// Which kind of difference made a state read back differently (review M2 U12): the
// notice in the browser gives an example that fits it, not always the same one. Found
// from the path where the editor's canonical form and the one read back first differ.

const LISTS = new Set(["bulletList", "taskList", "orderedList", "listItem", "taskItem"]);

/** The node at each step of the path in the form (the last is the differing value). */
function walk(form, keys) {
  const chain = [form];
  for (const key of keys) chain.push(chain.at(-1)?.[key]);
  return chain;
}

/** Whether a code run in the node holds a backslash. */
function backslashInCode(node) {
  if (Array.isArray(node)) return node.some(backslashInCode);
  if (!node || typeof node !== "object") return false;
  if (node.t === "text") return node.marks.includes("code") && node.text.includes("\\");
  return backslashInCode(node.content ?? node.inline ?? null);
}

const isLink = (key) => typeof key === "string" && key.startsWith("link");
const linked = (run) => run?.t === "text" && run.marks.some(isLink);

/** `tableCode` (code in a table cell holding a backslash: `\|` and `\\|` read as a
 * masked bar and a cell's end), `address` (a link the page view sets differently from
 * the editor: a bare address or e-mail address), `list` (a list read as another block,
 * e.g. empty nested items read as a rule), or null when none fits. */
export function causeOf(expected, back, where) {
  const keys = where.split(".");
  const mine = walk(expected, keys);
  const theirs = walk(back, keys);
  const steps = [...mine, ...theirs];
  const table = mine.find((node) => node?.type === "table");
  if (table && backslashInCode(table)) return "tableCode";
  const inline = keys.lastIndexOf("inline");
  if (inline !== -1) {
    const runs = (chain) => chain[inline + 1] ?? [];
    if ([...runs(mine), ...runs(theirs)].some(linked) || steps.some(isLink)) return "address";
  }
  if (keys.at(-1) === "type" && [mine.at(-1), theirs.at(-1)].some((type) => LISTS.has(type))) {
    return "list";
  }
  return null;
}
