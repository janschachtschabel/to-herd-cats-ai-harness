// Opening a page never changes it (review M2 T1/T2, ruling A): the collab process runs
// the browser's editor headless on the document it serves (`settle.mjs`). The headless
// editor sees what the browser's plugins do, and the document the server builds leaves
// them nothing to do.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import {
  jsonToMarkdown,
  jsonToYDoc,
  liveDocument,
  markdownToJSON,
  yDocToJSON,
} from "../markdown.mjs";
import { settle } from "../settle.mjs";

const text = (value, marks) => ({ type: "text", text: value, ...(marks ? { marks } : {}) });
const cell = (type, value) => ({
  type,
  attrs: { align: null },
  content: [{ type: "tableParagraph", content: value ? [text(value)] : [] }],
});
const row = (type, ...values) => ({ type: "tableRow", content: values.map((v) => cell(type, v)) });

test("the headless editor sees what the browser's plugins change on loading", () => {
  // A table with a short row, built as the parser built it before: the browser's table
  // repair makes the row as wide as the others, and that change would be sent.
  const ragged = {
    type: "doc",
    content: [{ type: "table", content: [row("tableHeader", "a", "b"), row("tableCell", "1")] }],
  };
  const result = settle(jsonToYDoc(ragged));
  assert.ok(result.update, "the browser would send an update");
  assert.equal(result.mutations > 0, true);
  assert.equal(jsonToMarkdown(result.json), "| a | b |\n| --- | --- |\n| 1 |  |");
});

test("the browser's update, applied to the served document, gives what it shows", () => {
  const ragged = {
    type: "doc",
    content: [{ type: "table", content: [row("tableHeader", "a", "b"), row("tableCell", "1")] }],
  };
  const served = jsonToYDoc(ragged);
  const { update, json } = settle(served);
  Y.applyUpdate(served, update);
  assert.equal(jsonToMarkdown(settle(served).json), jsonToMarkdown(json));
  assert.equal(settle(served).update, null);
});

const UNCHANGED = {
  "short row": "| a | b |\n| - | - |\n| 1 |\n",
  "table then text": "| a | b |\n| - | - |\n| 1 | 2 |\nText direkt danach\n",
  "long row": "| a | b |\n| - | - |\n| 1 | 2 | 3 |\n",
  "pipe in code": "| a | b |\n| - | - |\n| `x|y` | 2 |\n",
  "two pipes in code": "| Befehl | Bedeutung |\n| - | - |\n| `a || b` | oder |\n",
  "first heading a file": "# README.md\n\nText\n",
  "first heading a script": "# app.py\n\n- a\n- b\n",
  "domain at the end": "# Deployment auf example.com\n\nText\n",
  contact: "Kontakt: firma.de\n\nMehr\n",
  "list item": "- punkt.de\n- zwei\n",
  quote: "> zitat.com\n\nText\n",
  bold: "**fett.com**\n\nText\n",
  "second line": "Zeile eins\nzwei.de\n\nText\n",
  brief: "# Fix wave\n\nrulings on module-review-2.md\n\n## Next\n",
};

for (const [name, markdown] of Object.entries(UNCHANGED)) {
  test(`opening leaves nothing for the browser to change: ${name}`, () => {
    const opened = liveDocument(markdown);
    assert.ok(opened.safe, "opened");
    const result = settle(jsonToYDoc(opened.json));
    assert.equal(result.update, null, jsonToMarkdown(result.json));
    assert.equal(result.mutations, 0);
    assert.equal(result.invalid, null);
  });
}

test("a long row keeps every cell over its own heading", () => {
  const opened = liveDocument("| a | b |\n| - | - |\n| 1 | 2 | 3 |\n");
  assert.equal(jsonToMarkdown(opened.json), "| a | b |  |\n| --- | --- | --- |\n| 1 | 2 | 3 |");
});

test("an empty page holds one empty paragraph (undoing everything keeps it valid)", () => {
  const json = markdownToJSON("");
  assert.deepEqual(json, { type: "doc", content: [{ type: "paragraph" }] });
  assert.equal(settle(jsonToYDoc(json)).update, null);
});

/** A browser editor that rewrites a paragraph's text on loading (as a misbehaving
 * plugin would). */
function rewriting(from, to) {
  const walk = (node, parent) => {
    if (node.type === "text" && parent?.type === "paragraph" && node.text === from) {
      return { ...node, text: to };
    }
    return node.content ? { ...node, content: node.content.map((c) => walk(c, node)) } : node;
  };
  return (ydoc) => {
    const json = yDocToJSON(ydoc);
    const changed = walk(json);
    const same = JSON.stringify(changed) === JSON.stringify(json);
    return {
      json: changed,
      update: same ? null : new Uint8Array([1]),
      mutations: 0,
      invalid: null,
    };
  };
}

test("a change the browser makes on loading that keeps the meaning is served", () => {
  const opened = liveDocument("Text\n\nx y\n", { settleDoc: rewriting("x y", "x  y") });
  assert.ok(opened.safe);
  assert.equal(opened.json.content[1].content[0].text, "x  y");
});

test("a block the browser would change in meaning on loading is kept raw", () => {
  const opened = liveDocument("Text\n\ngeheim\n", { settleDoc: rewriting("geheim", "GEHEIM") });
  assert.ok(opened.safe);
  assert.deepEqual(opened.json.content[1], {
    type: "codeBlock",
    attrs: { language: "raw-markdown" },
    content: [{ type: "text", text: "geheim" }],
  });
  assert.equal(opened.json.content[0].type, "paragraph");
});

test("a page the browser would stop on is not opened", () => {
  const stops = (ydoc) => ({ json: yDocToJSON(ydoc), update: null, mutations: 0, invalid: "x" });
  assert.equal(liveDocument("Text\n", { settleDoc: stops }).safe, false);
});
