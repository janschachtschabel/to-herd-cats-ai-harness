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

// Two blocks that each save alone but not together (review M2 U1): the notice names
// the pair, not nothing.
test("two neighbours that fail only together are named as a pair", () => {
  const list = {
    type: "bulletList",
    content: [{ type: "listItem", content: [paragraph(text("a"))] }],
  };
  const indented = {
    type: "codeBlock",
    attrs: { language: "raw-markdown" },
    content: [text("  <b>x</b>")],
  };
  const result = readBack(doc(paragraph(text("Eins")), list, indented));
  assert.equal(result.ok, false);
  assert.equal(result.block, 1);
  assert.equal(result.through, 2);
});

test("the notice carries the block, or the pair", async () => {
  const { unrepresentableNotice } = await import("../protocol.mjs");
  assert.equal(
    unrepresentableNotice({ kind: "markdown", block: 2 }),
    "herd:unrepresentable:markdown:2",
  );
  assert.equal(
    unrepresentableNotice({ kind: "markdown", block: 1, through: 2 }),
    "herd:unrepresentable:markdown:1-2",
  );
  assert.equal(
    unrepresentableNotice({ kind: "unknown", block: null }),
    "herd:unrepresentable:unknown:",
  );
});

// Review M2 U12: the notice's example fits the cause the check found.
test("a state that reads back differently names a cause that fits", () => {
  const cases = [
    [doc(paragraph(text("Eins")), codeCell("a\\|")), "tableCode"],
    [doc(paragraph(text("anna@firma.de+bernd@firma.de"))), "address"],
    [doc(paragraph(text("a@e.g+@e.o~"))), "address"],
    [
      doc({
        type: "bulletList",
        content: [
          {
            type: "listItem",
            content: [
              paragraph(),
              {
                type: "bulletList",
                content: [
                  {
                    type: "listItem",
                    content: [
                      paragraph(),
                      {
                        type: "bulletList",
                        content: [{ type: "listItem", content: [paragraph()] }],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      }),
      "list",
    ],
  ];
  for (const [json, detail] of cases) {
    const result = readBack(json);
    assert.equal(result.ok, false);
    assert.equal(result.kind, "markdown");
    assert.equal(result.detail, detail, JSON.stringify(json));
  }
  assert.equal(readBack(doc(paragraph(text("Eins")))).detail, undefined);
});

test("the notice carries the cause after the place", async () => {
  const { unrepresentableNotice } = await import("../protocol.mjs");
  assert.equal(
    unrepresentableNotice({ kind: "markdown", block: 0, detail: "address" }),
    "herd:unrepresentable:markdown:0:address",
  );
  assert.equal(
    unrepresentableNotice({ kind: "markdown", block: null, detail: null }),
    "herd:unrepresentable:markdown:",
  );
});
