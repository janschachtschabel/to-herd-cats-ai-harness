// Tables in the live editor as GFM has them (review M2 T3): a row added in the editor
// takes its column's alignment, so the page stays saveable.
import { test } from "node:test";
import assert from "node:assert/strict";
import { Editor } from "@tiptap/core";
import { EditorState, TextSelection } from "@tiptap/pm/state";
import { addRowAfter } from "@tiptap/pm/tables";
import { liveDocument } from "../markdown.mjs";
import { readBack } from "../readback.mjs";
import { extensions } from "../schema.mjs";

/** An editor state with the editor's plugins, the cursor in the last cell. */
function stateOf(markdown) {
  const json = liveDocument(markdown).json;
  const editor = new Editor({ element: null, content: json, extensions: extensions() });
  const plugins = editor.extensionManager.plugins;
  let state = EditorState.create({ doc: editor.state.doc, plugins });
  let last = 0;
  state.doc.descendants((node, pos) => {
    if (node.type.name === "tableParagraph") last = pos + 1;
  });
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, last)));
  editor.destroy();
  return state;
}

test("a row added to a table takes each column's alignment", () => {
  let state = stateOf("| Name | Wert |\n| --- | --: |\n| a | 1 |\n");
  assert.ok(addRowAfter(state, (tr) => (state = state.apply(tr))));
  const table = state.doc.firstChild;
  assert.equal(table.childCount, 3);
  assert.deepEqual(
    table.lastChild.content.content.map((cell) => cell.attrs.align),
    [null, "right"],
  );
  const written = readBack(state.doc.toJSON());
  assert.ok(written.ok, written.problem);
  assert.equal(written.markdown, "| Name | Wert |\n| --- | --: |\n| a | 1 |\n|  |  |");
});
