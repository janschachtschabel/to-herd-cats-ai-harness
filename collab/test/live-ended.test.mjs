// A login session that ends is not a revocation (review M2 R2): what its person typed
// is saved, only their connection closes, the others go on in the same generation.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

// Saves only every 30 s: anything saved earlier was saved on purpose.
const start = async () =>
  (live = await liveFixture({ createCollabServer, debounceMs: 30_000, maxDebounceMs: 60_000 }));

const ok = (extra = {}) => [
  200,
  {
    generation_ok: true,
    generation: 0,
    revoked_session_ids: [],
    revoked_user_ids: [],
    ended_session_ids: [],
    ...extra,
  },
];

test("a connection that leaves with unsaved edits is saved at once", async () => {
  await start();
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  await until(() => live.api.saves.length === 1);
  type(anna.doc, " Annas Satz");
  await until(() => ben.doc.getXmlFragment("default").toString().includes("Annas Satz"));
  anna.destroy();
  await until(() => live.api.saves.length === 2, 2000);
  assert.match(live.api.saves[1].content_md, /Annas Satz/);
  assert.deepEqual(live.api.saves[1].editor_session_ids, ["session-a"]);
  assert.deepEqual(ben.closes, []);
});

test("an ended session's edits are saved, then only its connection closes (4401)", async () => {
  await start();
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(anna), synced(ben)]);
  await until(() => live.api.saves.length === 1);
  type(anna.doc, " Annas Satz");
  type(ben.doc, " Bens Text");
  await until(() =>
    ["Annas Satz", "Bens Text"].every((t) =>
      ben.doc.getXmlFragment("default").toString().includes(t),
    ),
  );
  live.api.checkAnswer = () => ok({ ended_session_ids: ["session-a"] }); // Anna logged out
  await until(() => anna.closes.includes(4401));
  live.api.checkAnswer = () => ok();
  const saved = live.api.saves[1];
  assert.match(saved.content_md, /Annas Satz/);
  assert.match(saved.content_md, /Bens Text/);
  assert.deepEqual([...saved.editor_session_ids].sort(), ["session-a", "session-b"]);
  assert.equal(saved.generation, 0);
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.deepEqual(ben.closes, [], "Ben goes on in the same generation");
  type(ben.doc, " weiter");
  await until(() => {
    live.server.hocuspocus.flushPendingStores();
    return live.api.saves.some((s) => s.content_md.includes("weiter"));
  });
});

/** The client's "I am done" (review M2 R3): the server saves and answers when stored. */
function finish(c) {
  return new Promise((resolve) => {
    const answer = ({ payload }) => {
      c.provider.off("stateless", answer);
      resolve(payload);
    };
    c.provider.on("stateless", answer);
    c.provider.sendStateless("herd:flush");
  });
}

test("a client that is done gets its edits saved before it leaves", { timeout: 8000 }, async () => {
  await start();
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  await until(() => live.api.saves.length === 1);
  type(anna.doc, " fertig");
  await until(() => !anna.provider.hasUnsyncedChanges);
  assert.equal(await finish(anna), "herd:saved");
  assert.equal(live.api.saves.length, 2);
  assert.match(live.api.saves[1].content_md, /fertig/);
  // Nothing new: answered at once, nothing saved again.
  assert.equal(await finish(anna), "herd:saved");
  assert.equal(live.api.saves.length, 2);
});

test("a flush that cannot be saved says so", { timeout: 8000 }, async () => {
  await start();
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  await until(() => live.api.saves.length === 1);
  live.api.saveAnswer = () => [503, {}];
  type(anna.doc, " offen");
  await until(() => !anna.provider.hasUnsyncedChanges);
  assert.equal(await finish(anna), "herd:unsaved");
  live.api.saveAnswer = () => [200, { generation: 0, version: 2 }]; // the API is back
  assert.equal(await finish(anna), "herd:unsaved", "at most one forced save per second");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  assert.equal(await finish(anna), "herd:saved");
  assert.match(live.api.saves.at(-1).content_md, /offen/);
});
