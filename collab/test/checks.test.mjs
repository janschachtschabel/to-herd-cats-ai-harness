// The heavy checks run on worker threads (review M2 T9): the answers are those of the
// functions themselves, and the event loop goes on while a large page is checked.
import { after, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { createChecks, inlineChecks } from "../checks.mjs";
import { jsonToYDoc, markdownToJSON, yDocToJSON } from "../markdown.mjs";

const checks = createChecks({ workers: 2 });
const inline = inlineChecks();
after(() => checks.close());

const PAGE =
  "# Titel\n\nText mit **fett** und `code`.\n\n| a | b |\n| - | - |\n| 1 |\n\n- eins\n- zwei\n";

/** A page of about `chars` characters of varied blocks. */
function largePage(chars) {
  const blocks = [];
  for (let i = 0; blocks.join("\n\n").length < chars; i++) {
    blocks.push(
      `## Abschnitt ${i}`,
      `Absatz ${i} mit *Betonung*, einem [Link](https://example.com/${i}) und Text. `.repeat(6),
      `- Punkt ${i}\n- noch einer\n  - eingerückt`,
      "```js\nconst x = " + i + ";\n```",
    );
    if (i % 10 === 0) blocks.push(`| Spalte | Wert |\n| --- | ---: |\n| ${i} | ${i * 2} |`);
  }
  return blocks.join("\n\n") + "\n";
}

test("a worker opens a page as this thread does", async () => {
  const [worked, here] = await Promise.all([checks.open(PAGE), inline.open(PAGE)]);
  assert.equal(worked.safe, true);
  assert.equal(worked.baseline, here.baseline);
  assert.deepEqual(yDocToJSON(docOf(worked.update)), yDocToJSON(docOf(here.update)));
});

function docOf(update) {
  const doc = new Y.Doc();
  Y.applyUpdate(doc, update);
  return doc;
}

test("a worker tidies a stored state as this thread does", async () => {
  const ragged = jsonToYDoc({
    type: "doc",
    content: [
      {
        type: "table",
        content: [
          { type: "tableRow", content: [cell("tableHeader", "a"), cell("tableHeader", "b")] },
          { type: "tableRow", content: [cell("tableCell", "1")] },
        ],
      },
    ],
  });
  const stored = Y.encodeStateAsUpdate(ragged);
  const worked = await checks.tidy(stored);
  const here = await inline.tidy(stored);
  assert.equal(worked.problem, null);
  assert.ok(worked.update, "the short row is tidied");
  assert.equal(worked.baseline, here.baseline);
  assert.equal(worked.baseline, "| a | b |\n| --- | --- |\n| 1 |  |");
});

function cell(type, value) {
  return {
    type,
    attrs: { align: null },
    content: [{ type: "tableParagraph", content: [{ type: "text", text: value }] }],
  };
}

test("a worker's save check answers as this thread's", async () => {
  const json = markdownToJSON(PAGE);
  assert.deepEqual(await checks.readBack(json), await inline.readBack(json));
});

test("a failing check fails only its own request", async () => {
  await assert.rejects(checks.tidy(new Uint8Array([255, 255, 255, 255])));
  assert.equal((await checks.open("Text\n")).safe, true);
});

test("the event loop goes on while a page of 200,000 characters is checked", async () => {
  const markdown = largePage(195_000);
  assert.ok(markdown.length > 190_000 && markdown.length <= 200_000, `${markdown.length}`);
  const json = markdownToJSON(markdown);
  let longest = 0;
  let last = performance.now();
  const timer = setInterval(() => {
    const now = performance.now();
    longest = Math.max(longest, now - last);
    last = now;
  }, 10);
  const started = performance.now();
  const opened = await checks.open(markdown);
  const written = await checks.readBack(json);
  clearInterval(timer);
  assert.equal(opened.safe, true);
  assert.equal(written.ok, true);
  const took = performance.now() - started;
  // Only handing the work over and taking the answer run here; the checks themselves
  // (seconds) do not.
  assert.ok(
    longest < 100,
    `the event loop stalled ${Math.round(longest)} ms of ${Math.round(took)}`,
  );
});
