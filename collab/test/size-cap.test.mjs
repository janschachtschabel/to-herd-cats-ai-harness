// The live document is capped between saves (review M2 R9): an update that would
// take the state or its Markdown over the limit is refused, only its sender is
// closed (4413), everyone else goes on.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const text = (c) => c.doc.getXmlFragment("default").toString();

for (const [label, limits] of [
  ["Markdown characters", { maxMarkdownChars: 400 }],
  ["state bytes", { maxStateBytes: 1500 }],
]) {
  test(`an update over the ${label} limit closes only its sender`, async () => {
    live = await liveFixture({ createCollabServer, ...limits });
    const anna = live.open({ cookie: "herd_session=token-a" });
    const ben = live.open({ cookie: "herd_session=token-b" });
    await Promise.all([synced(anna), synced(ben)]);
    await until(() => live.api.saves.length === 1);
    type(anna.doc, " klein");
    await until(() => text(ben).includes("klein"));
    type(anna.doc, "x".repeat(2000));
    await until(() => anna.closes.includes(4413));
    type(ben.doc, " weiter");
    await until(() => {
      live.server.hocuspocus.flushPendingStores();
      return live.api.saves.some((s) => s.content_md.includes("weiter"));
    });
    assert.ok(!text(ben).includes("xxxx"), "the refused update reached no one");
    assert.ok(live.api.saves.every((s) => !s.content_md.includes("xxxx")));
    assert.deepEqual(ben.closes, []);
  });
}

test("the size is measured exactly before an update is admitted (review M2 S5)", async () => {
  // 300 characters fit under a limit of 400: admitted, though a rough estimate of what
  // the update could add would refuse it. 200 more do not fit: refused.
  live = await liveFixture({ createCollabServer, maxMarkdownChars: 400, measureEveryMs: 0 });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  type(anna.doc, ` ${"a".repeat(300)}`);
  await until(() => live.api.saves.some((s) => s.content_md.includes("a".repeat(300))));
  assert.deepEqual(anna.closes, []);
  type(anna.doc, "b".repeat(200));
  await until(() => anna.closes.includes(4413));
  assert.ok(live.api.saves.every((s) => !s.content_md.includes("bbbb")));
});

test("a long text in one cell of a long table keeps the session (review M2 S5)", async () => {
  const rows = Array.from({ length: 400 }, (_, i) => `| ${i} | Artikel ${i} |`);
  const markdown = ["| Nr | Name |", "| --- | --- |", ...rows].join("\n");
  live = await liveFixture({ markdown, createCollabServer });
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  const table = anna.doc.getXmlFragment("default").get(0);
  const cell = table.get(1).get(1).get(0).get(0); // row 0, column "Name": its text
  const note = " Hinweis: bitte vor der Ausgabe prüfen.".repeat(16); // 608 characters
  cell.insert(cell.length, note);
  await until(() => live.api.saves.some((s) => s.content_md.includes(note.trim())));
  const stored = live.api.saves.at(-1).content_md;
  // Stored in proportion to the content: the note once, no padding of other rows.
  assert.ok(stored.length < markdown.length + note.length + 10, `${stored.length} characters`);
  assert.deepEqual(anna.closes, []);
  assert.deepEqual(ben.closes, []);
});

test("a document is measured exactly at most once per interval (review M2 S10, T12)", async () => {
  // Near the limit every update needs a measurement of the whole document: one within
  // the interval waits for its end and is measured then, its sender stays (T12).
  live = await liveFixture({ createCollabServer, maxMarkdownChars: 400, measureEveryMs: 600 });
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  type(anna.doc, ` ${"a".repeat(300)}`);
  await until(() => text(ben).includes("a".repeat(300)));
  const typed = Date.now();
  type(anna.doc, "b");
  type(anna.doc, "c");
  await until(() => text(ben).includes("bc"));
  assert.ok(Date.now() - typed >= 300, `admitted after ${Date.now() - typed} ms`);
  assert.deepEqual(anna.closes, []);
  // Over the limit after the wait: refused as before.
  type(anna.doc, "d".repeat(200));
  await until(() => anna.closes.includes(4413));
  assert.ok(!text(ben).includes("ddd"));
  assert.deepEqual(ben.closes, []);
});
