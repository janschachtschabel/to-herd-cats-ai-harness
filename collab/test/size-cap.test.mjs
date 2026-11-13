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
