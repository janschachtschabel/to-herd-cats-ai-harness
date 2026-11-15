// What a refused save tells the browsers (review M2 R8): 413 → 4413 `too_large` (the
// editor says the page is too large for live editing); any other refusal is a neutral
// stop (4400), never "not found".
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

for (const [status, code] of [
  [413, 4413],
  [422, 4400],
  [400, 4400],
  [404, 4404],
]) {
  test(`a save answered ${status} closes everyone with ${code}`, async () => {
    live = await liveFixture({ createCollabServer });
    const anna = live.open({ grant: "herd_cg_a" });
    const ben = live.open({ grant: "herd_cg_b" });
    await Promise.all([synced(anna), synced(ben)]);
    await until(() => live.api.saves.length === 1);
    live.api.saveAnswer = () => [status, { error: { code: "x" } }];
    type(anna.doc, " mehr");
    await until(() => anna.closes.includes(code) && ben.closes.includes(code));
    assert.ok(live.api.saves.length >= 2);
  });
}
