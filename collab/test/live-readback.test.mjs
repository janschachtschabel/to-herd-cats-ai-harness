// A live save stores only Markdown that reads back as what the editors see (review M2
// S2, S3, invariant B): a state that cannot be written so is not stored, counted at the
// API, and every editor is told (a notice that does not close the session) until a
// later state saves again.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { createCollabServer } from "../server.mjs";
import { FLUSH, REPRESENTABLE, SAVED, UNREPRESENTABLE, UNSAVED } from "../protocol.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const TABLE = "| `a` |\n| --- |";

/** The code text in the table's only cell. */
function cellText(doc) {
  return doc.getXmlFragment("default").get(0).get(0).get(0).get(0).get(0);
}

function listen(c) {
  const messages = [];
  c.provider.on("stateless", ({ payload }) => messages.push(payload));
  return messages;
}

test("a state that cannot be written as Markdown is not stored, and everyone is told", async () => {
  live = await liveFixture({ markdown: TABLE, createCollabServer });
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  const annaHears = listen(anna);
  const benHears = listen(ben);
  const stored = live.api.saves.length;

  // Code ending in a backslash right before `|` in a table cell: no Markdown says it.
  const text = cellText(anna.doc);
  const [{ attributes }] = text.toDelta();
  Y.transact(anna.doc, () => text.insert(text.length, "\\|", attributes));

  await until(() => annaHears.includes(UNREPRESENTABLE) && benHears.includes(UNREPRESENTABLE));
  await until(() => live.api.unrepresentable >= 1);
  assert.equal(live.api.saves.length, stored, "nothing stored for that state");
  assert.deepEqual(anna.closes, [], "the session goes on");
  anna.provider.sendStateless(FLUSH);
  await until(() => annaHears.includes(UNSAVED));
  assert.ok(!annaHears.includes(SAVED));

  // A later state that can be written is stored, and the notice clears.
  Y.transact(anna.doc, () => text.delete(text.length - 2, 1)); // the backslash
  await until(() => live.api.saves.length > stored);
  assert.equal(live.api.saves.at(-1).content_md, "| `a\\|` |\n| --- |");
  await until(() => annaHears.includes(REPRESENTABLE) && benHears.includes(REPRESENTABLE));
});

test("someone joining a document that cannot be saved is told at once", async () => {
  live = await liveFixture({ markdown: TABLE, createCollabServer });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  const text = cellText(anna.doc);
  const [{ attributes }] = text.toDelta();
  Y.transact(anna.doc, () => text.insert(text.length, "\\|", attributes));
  await until(() => live.api.unrepresentable >= 1);
  const ben = live.open({ cookie: "herd_session=token-b" });
  const benHears = listen(ben);
  await until(() => benHears.includes(UNREPRESENTABLE));
});
