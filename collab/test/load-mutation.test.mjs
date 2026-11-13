// A browser's editor that changes a document it has just loaded, before the person did
// anything, stops instead of sending the change and says so (review M2 ruling B): the
// collab process counts it at the API, once per connection.
import { afterEach, test } from "node:test";
import { createCollabServer } from "../server.mjs";
import { LOAD_MUTATION } from "../protocol.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";
import assert from "node:assert/strict";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test("a load mutation is counted once per connection, nothing is stored", async () => {
  live = await liveFixture({ markdown: "Text", createCollabServer });
  const c = live.open({ cookie: "herd_session=token-a" });
  await synced(c);
  const saves = live.api.saves.length;
  c.provider.sendStateless(LOAD_MUTATION);
  c.provider.sendStateless(LOAD_MUTATION);
  await until(() => live.api.loadMutations === 1);
  await pause(100);
  assert.equal(live.api.loadMutations, 1);
  assert.equal(live.api.saves.length, saves);
});
