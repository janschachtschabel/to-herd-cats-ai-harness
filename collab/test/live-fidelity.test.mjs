// A live session never changes a page by itself (review M2 R1): pages the editor
// cannot show without changing them are refused with 4422, and opening and closing
// the editor without an edit leaves the stored Markdown exactly as it was.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as Y from "yjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const start = async (markdown) => (live = await liveFixture({ markdown, createCollabServer }));
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test("a page that would change its meaning is not opened (4422)", async () => {
  // The parser reads the second line as a paragraph; written after the code block as a
  // block of its own (raw, for its HTML) it would be a list.
  await start("    b\n0. <x>");
  const c = live.open({ cookie: "herd_session=token-a" });
  await until(() => c.closes.includes(4422));
  assert.ok(!c.provider.synced);
  assert.equal(live.api.saves.length, 0, "nothing saved");
});

// Markdown the serializer writes differently (bullets, table padding, entities).
const UNTIDY = "* eins\n* zwei\n\n| a |\n|---|\n| 1 |\n\n&copy; 2026, Titel\n=====";

test("opening and closing the live editor without typing changes nothing", async () => {
  await start(UNTIDY);
  const c = live.open({ cookie: "herd_session=token-a" });
  await synced(c);
  await pause(400); // longer than the save debounce
  c.destroy();
  await until(() => live.server.hocuspocus.getDocumentsCount() === 0);
  assert.ok(live.api.saves.length >= 1);
  for (const save of live.api.saves) assert.equal(save.content_md, UNTIDY);
});

test("a structural change without a change of meaning keeps the stored Markdown", async () => {
  await start(UNTIDY);
  const c = live.open({ cookie: "herd_session=token-a" });
  await synced(c);
  // An edit that is undone again: the document's history changed, its Markdown not.
  type(c.doc, "!");
  await until(() => live.api.saves.some((s) => s.content_md !== UNTIDY));
  const fragment = c.doc.getXmlFragment("default");
  const text = fragment
    .toArray()
    .find((node) => node.nodeName === "paragraph")
    .get(0);
  Y.transact(c.doc, () => text.delete(text.length - 1, 1));
  await until(() => live.api.saves.at(-1).content_md === UNTIDY);
});

test("a stored live state the editor's schema does not allow is not opened (4422)", async () => {
  // E.g. kept from an older release: a paragraph holding a block. The browser would
  // delete it and that deletion would be saved (review M2 S1: never a repaired document).
  await start("Text");
  const doc = new Y.Doc();
  const paragraph = new Y.XmlElement("paragraph");
  paragraph.insert(0, [new Y.XmlElement("horizontalRule")]);
  doc.getXmlFragment("default").insert(0, [paragraph]);
  live.api.ydoc = Buffer.from(Y.encodeStateAsUpdate(doc)).toString("base64");
  const c = live.open({ cookie: "herd_session=token-a" });
  await until(() => c.closes.includes(4422));
  assert.equal(live.api.saves.length, 0, "nothing saved");
});
