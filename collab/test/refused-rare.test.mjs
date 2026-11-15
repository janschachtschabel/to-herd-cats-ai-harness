// Rare states the save check refuses although nobody did anything wrong (review M2 U7,
// from the generative run with seed 313131). Ruled: no change; they stay refused, are
// told, and nothing is stored. The third case of the review (an address followed by the
// same address struck through, then a second list) is saved since U1 gave the second
// list another marker: it is pinned as saved and reopening unchanged.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { liveDocument } from "../markdown.mjs";
import { UNREPRESENTABLE } from "../protocol.mjs";
import { readBack } from "../readback.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const text = (value, marks) => ({ type: "text", text: value, ...(marks && { marks }) });
const paragraph = (...content) => ({ type: "paragraph", content });
const item = (...content) => ({ type: "listItem", content });
const bullets = (...items) => ({ type: "bulletList", content: items });
const doc = (...content) => ({ type: "doc", content });

const RARE = {
  // Two addresses joined by `+`: the page view links the first only.
  "two e-mail addresses joined by +": [
    doc(paragraph(text("anna@firma.de+bernd@firma.de"))),
    "address",
  ],
  // Three nested empty bullets are written `- - -`, which Markdown reads as a rule.
  "three nested empty bullets": [
    doc(bullets(item(paragraph(), bullets(item(paragraph(), bullets(item(paragraph()))))))),
    "list",
  ],
};

/** The editor's JSON as Y.Doc nodes, as a browser's binding writes them (for blocks
 * holding at most one text node, as these cases do). */
function yNode(node) {
  if (node.type === "text") {
    const yText = new Y.XmlText();
    const marks = Object.fromEntries((node.marks ?? []).map((mark) => [mark.type, {}]));
    yText.insert(0, node.text, marks);
    return yText;
  }
  const element = new Y.XmlElement(node.type);
  element.insert(0, (node.content ?? []).map(yNode)); // one text node per block here
  return element;
}

for (const [name, [json, detail]] of Object.entries(RARE)) {
  test(`refused, nothing stored: ${name}`, async () => {
    const answer = readBack(json);
    assert.equal(answer.ok, false);
    assert.equal(answer.kind, "markdown");
    assert.equal(answer.block, 0);

    live = await liveFixture({ markdown: "Start", createCollabServer, checkWorkers: 0 });
    const anna = live.open({ grant: "herd_cg_a" });
    await synced(anna);
    const heard = [];
    anna.provider.on("stateless", ({ payload }) => heard.push(payload));
    const stored = live.api.saves.length;
    const fragment = anna.doc.getXmlFragment("default");
    Y.transact(anna.doc, () => {
      fragment.delete(0, fragment.length);
      fragment.insert(0, json.content.map(yNode));
    });
    await until(() => heard.includes(`${UNREPRESENTABLE}:markdown:0:${detail}`));
    live.server.hocuspocus.flushPendingStores();
    await until(() => live.api.unrepresentable >= 1);
    assert.equal(live.api.saves.length, stored, "nothing stored");
    assert.deepEqual(anna.closes, [], "the session goes on");
  });
}

test("an address and the same address struck through, then a list: saved since U1", () => {
  const json = doc(
    bullets(item(paragraph(text("https://a.de"), text("https://a.de", [{ type: "strike" }])))),
    bullets(item(paragraph(text("x")))),
  );
  const answer = readBack(json);
  assert.equal(answer.ok, true, answer.problem);
  const reopened = liveDocument(answer.markdown);
  assert.equal(reopened.safe, true);
});
