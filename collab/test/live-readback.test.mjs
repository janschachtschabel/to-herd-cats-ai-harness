// A live save stores only Markdown that reads back as what the editors see (review M2
// S2, S3, invariant B): a state that cannot be written so is not stored, counted at the
// API, and every editor is told (a notice that does not close the session) until a
// later state saves again.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { createCollabServer } from "../server.mjs";
import { FLUSH, REPRESENTABLE, SAVED, STORED, UNREPRESENTABLE, UNSAVED } from "../protocol.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const TABLE = "| `a` |\n| --- |";
// The notice names the kind of cause, the block (the table, block 0) and the kind of
// difference (code with a backslash in a table cell, review M2 U12).
const NOTICE = `${UNREPRESENTABLE}:markdown:0:tableCode`;

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

  await until(() => annaHears.includes(NOTICE) && benHears.includes(NOTICE));
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
  await until(() => benHears.includes(NOTICE));
});

/** Whether the stored snapshot holds every change the client made (its own clock and
 * everything it deleted). */
function holds(payload, doc, deleted) {
  const snapshot = Y.decodeSnapshot(Buffer.from(payload.slice(STORED.length), "base64"));
  if ((snapshot.sv.get(doc.clientID) ?? 0) < Y.getState(doc.store, doc.clientID)) return false;
  return deleted.every((id) => Y.isDeleted(snapshot.ds, id));
}

test("every stored state is acknowledged to everyone; a refused one is not (T5)", async () => {
  live = await liveFixture({ markdown: TABLE, createCollabServer });
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  const annaHears = listen(anna);
  const benHears = listen(ben);
  const text = cellText(anna.doc);
  const [{ attributes }] = text.toDelta();
  Y.transact(anna.doc, () => text.insert(text.length, "x", attributes));
  const stored = () => annaHears.filter((p) => p.startsWith(STORED));
  await until(() => stored().some((p) => holds(p, anna.doc, [])));
  await until(() => benHears.some((p) => p.startsWith(STORED)));

  // A refused state: no acknowledgement holds it.
  const before = stored().length;
  Y.transact(anna.doc, () => text.insert(text.length, "\\|", attributes));
  await until(() => annaHears.includes(NOTICE));
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.ok(
    stored()
      .slice(before)
      .every((p) => !holds(p, anna.doc, [])),
  );

  // Deleting it again is stored: the acknowledgement holds the deletion too.
  Y.transact(anna.doc, () => text.delete(text.length - 2, 2));
  const deleted = [new Y.ID(anna.doc.clientID, Y.getState(anna.doc.store, anna.doc.clientID) - 1)];
  await until(() => stored().some((p) => holds(p, anna.doc, deleted)));
});
