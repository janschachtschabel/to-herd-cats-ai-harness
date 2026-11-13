// A state that cannot be saved names the kind of cause and the block (review M2 fix
// wave 3): the notice in the browser says what is wrong and where, as far as the save
// check knows it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readBack } from "../readback.mjs";

const text = (value, ...marks) => ({
  type: "text",
  text: value,
  ...(marks.length && { marks: marks.map((type) => ({ type })) }),
});
const paragraph = (...content) => ({ type: "paragraph", content });
const doc = (...content) => ({ type: "doc", content });
const codeCell = (value) => ({
  type: "table",
  content: [
    {
      type: "tableRow",
      content: [
        {
          type: "tableHeader",
          attrs: { align: null },
          content: [{ type: "tableParagraph", content: [text(value, "code")] }],
        },
      ],
    },
  ],
});

test("Markdown that reads back differently names its block", () => {
  const result = readBack(doc(paragraph(text("Eins")), paragraph(text("Zwei")), codeCell("a\\|")));
  assert.equal(result.ok, false);
  assert.equal(result.kind, "markdown");
  assert.equal(result.block, 2);
});

test("a structure the editor cannot hold names its block", () => {
  const result = readBack(doc(paragraph(text("Eins")), { type: "bulletList", content: [] }));
  assert.equal(result.ok, false);
  assert.equal(result.kind, "structure");
  assert.equal(result.block, 1);
});

test("a state that saves names nothing", () => {
  const result = readBack(doc(paragraph(text("Eins")), paragraph(text("Zwei"))));
  assert.deepEqual(result, { ok: true, markdown: "Eins\n\nZwei" });
});
