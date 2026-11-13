// A list next to a raw block whose source is a list (review M2 U1): the serializer
// gives the list a marker the raw block's neighbouring list does not use, so Markdown
// reads the two as two lists. Before, the new list took `-` like the raw one and both
// were read as one list: the page could not be saved (or, stored so, not opened).
import { test } from "node:test";
import assert from "node:assert/strict";
import { liveDocument, markdownToJSON } from "../markdown.mjs";
import { readBack } from "../readback.mjs";
import { rawBlock } from "../parse.mjs";

const text = (value) => ({ type: "text", text: value });
const paragraph = (...content) => ({ type: "paragraph", content });
const doc = (...content) => ({ type: "doc", content });
const bullets = (...values) => ({
  type: "bulletList",
  content: values.map((value) => ({ type: "listItem", content: [paragraph(text(value))] })),
});
const tasks = (...values) => ({
  type: "taskList",
  content: values.map((value) => ({
    type: "taskItem",
    attrs: { checked: false },
    content: [paragraph(text(value))],
  })),
});
const ordered = (...values) => ({
  type: "orderedList",
  attrs: { start: 1 },
  content: values.map((value) => ({ type: "listItem", content: [paragraph(text(value))] })),
});

const MIXED = "- [ ] **Schritt 1**\n- Hinweis dazu";
const HTML = "- <kbd>Strg</kbd>+C kopiert";

test("the stored mixed list is a raw block (T14), the premise of these cases", () => {
  const { json } = liveDocument(`# Plan\n\n${MIXED}\n`);
  assert.equal(json.content[1].attrs.language, "raw-markdown");
});

test("a bullet list typed after a raw list saves as a list of its own", () => {
  const result = readBack(doc(rawBlock(MIXED), bullets("neuer Punkt")));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, `${MIXED}\n\n* neuer Punkt`);
});

test("a task list typed after a raw list saves", () => {
  const result = readBack(doc(rawBlock(MIXED), tasks("noch offen")));
  assert.equal(result.ok, true, result.problem);
});

test("a list typed before a raw list holding HTML saves", () => {
  const result = readBack(doc(bullets("davor"), rawBlock(HTML)));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, `* davor\n\n${HTML}`);
});

test("a list between two raw lists takes the marker neither uses", () => {
  const result = readBack(doc(rawBlock(HTML), bullets("mitten"), rawBlock("* <b>x</b>")));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, `${HTML}\n\n+ mitten\n\n* <b>x</b>`);
});

test("an ordered list after a raw ordered list takes the other delimiter", () => {
  const result = readBack(doc(rawBlock("1. <b>eins</b>"), ordered("zwei")));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, "1. <b>eins</b>\n\n1) zwei");
});

test("a raw block that is not a list leaves the markers alone", () => {
  const result = readBack(doc(rawBlock("<div>x</div>"), bullets("a"), bullets("b")));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, "<div>x</div>\n\n- a\n\n* b");
});

test("stored pages with a list next to a raw list open live (were 4422)", () => {
  for (const markdown of [
    "- <kbd>Strg</kbd>+C\n\n* zweite Liste\n",
    "- [ ] a\n- b\n\n* zweite Liste\n",
    "* zweite Liste\n\n- <kbd>Strg</kbd>+C\n",
  ]) {
    const opened = liveDocument(markdown);
    assert.equal(opened.safe, true, markdown);
    assert.ok(
      opened.json.content.some((block) => block.type === "bulletList"),
      `the plain list is editable: ${markdown}`,
    );
  }
});

test("a list after a raw block made of several blocks looks at its last one", () => {
  const raw = "<div>x</div>\n\n- <b>y</b>";
  assert.equal(markdownToJSON(raw).content.length, 2); // two top-level blocks
  const result = readBack(doc(rawBlock(raw), bullets("z")));
  assert.equal(result.ok, true, result.problem);
  assert.equal(result.markdown, `${raw}\n\n* z`);
});
