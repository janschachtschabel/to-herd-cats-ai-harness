// Several collab instances (plan M9 task 15, decision 17): an instance announces
// itself, names itself (and the epoch of its binding) in every call for a page, drops a
// document it no longer owns, and on SIGTERM drains: no new pages, everything saved,
// its pages released, then the browsers reconnect (to another instance).
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { createCollabServer } from "../server.mjs";
import { PAGE, liveFixture, synced, type, until } from "./helpers.mjs";

const ID = "0190a1d2-0000-7000-8000-00000000000a";
const URL_ = "ws://10.0.0.7:1234";
let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

function start(options = {}) {
  return liveFixture({
    createCollabServer,
    instanceId: ID,
    advertiseUrl: URL_,
    heartbeatMs: 50,
    ...options,
  });
}

test("an instance announces itself and names itself in every call for a page", async () => {
  live = await start();
  await until(() => live.api.announcements.length >= 3);
  assert.deepEqual(live.api.announcements[0], { id: ID, url: URL_, draining: false });
  live.api.epoch = 7;
  const c = live.open({ grant: "herd_cg_a" });
  await synced(c);
  type(c.doc, "Hallo");
  await until(() => live.api.saves.length > 0 && live.api.checks.length > 0);
  assert.equal(live.api.auths[0].instance_id, ID);
  assert.deepEqual(live.api.loadInstances, [ID]);
  for (const call of [...live.api.saves, ...live.api.checks]) {
    assert.equal(call.instance_id, ID);
    assert.equal(call.epoch, 7);
  }
});

test("without an address the process names no instance (as 1.0.0 did)", async () => {
  live = await start({ instanceId: undefined, advertiseUrl: null });
  const c = live.open({ grant: "herd_cg_a" });
  await synced(c);
  type(c.doc, "Hallo");
  await until(() => live.api.saves.length > 0 && live.api.checks.length > 0);
  assert.deepEqual(live.api.announcements, []);
  assert.equal(live.api.auths[0].instance_id, undefined);
  assert.deepEqual(live.api.loadInstances, [null]);
  for (const call of [...live.api.saves, ...live.api.checks]) {
    assert.ok(!("instance_id" in call) && !("epoch" in call));
  }
});

test("a save refused as not the owner drops the document and closes with 4409", async () => {
  live = await start();
  const c = live.open({ grant: "herd_cg_a" });
  await synced(c);
  live.api.saveAnswer = () => [409, { error: { code: "collab.not_owner" } }];
  live.api.checkAnswer = () => [200, { generation_ok: true, generation: 0 }];
  type(c.doc, "verloren");
  await until(() => c.closes.includes(4409));
  assert.equal(live.server.extension.live.size, 0);
});

test("a check refused as not the owner drops the document and closes with 4409", async () => {
  live = await start();
  const c = live.open({ grant: "herd_cg_a" });
  await synced(c);
  live.api.checkAnswer = () => [409, { error: { code: "collab.not_owner" } }];
  await until(() => c.closes.includes(4409));
  await until(() => live.server.extension.live.size === 0);
});

test("a connection admitted under a newer epoch drops the outdated document", async () => {
  live = await start();
  const first = live.open({ grant: "herd_cg_a" });
  await synced(first);
  // The page was bound anew to this instance meanwhile (it lost and won it back): the
  // document in memory belongs to the old binding and could not be saved anyway.
  live.api.epoch = 2;
  const second = live.open({ grant: "herd_cg_b" });
  await until(() => first.closes.includes(4409));
  await until(() => live.server.extension.live.get(`page:${PAGE}`)?.epoch === 2);
  await synced(second);
});

test("on close the instance drains: no new pages, saves, releases, then closes", async () => {
  live = await start();
  const c = live.open({ grant: "herd_cg_a" });
  await synced(c);
  live.api.sequence.length = 0;
  type(c.doc, "noch schnell");
  await live.server.close();
  assert.ok(c.closes.includes(1012), JSON.stringify(c.closes));
  const order = live.api.sequence.filter((step) => step !== "announce");
  assert.equal(order[0], "announce:draining");
  assert.ok(order.includes("save"));
  assert.equal(order.at(-1), "release");
  assert.ok(order.indexOf("save") < order.indexOf("release"));
  assert.deepEqual(live.api.releases, [ID]);
  assert.match(live.api.saves.at(-1).content_md, /noch schnell/);
  // No heartbeat after the release brings it back.
  const announced = live.api.announcements.length;
  await new Promise((resolve) => setTimeout(resolve, 200));
  assert.equal(live.api.announcements.length, announced);
});
