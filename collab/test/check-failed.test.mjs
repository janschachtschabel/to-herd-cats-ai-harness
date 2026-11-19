// A page too heavy to check on a check worker (its heap is capped, `checks.mjs`) is
// too large for live editing when opened (4413), and a state too heavy to check on
// saving is not stored, with the notice of an unsaveable state of unknown cause.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { CheckFailed, inlineChecks } from "../checks.mjs";
import { UNREPRESENTABLE } from "../protocol.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

/** Checks as on this thread, but the ones named fail as a worker out of memory. */
function failing(...kinds) {
  const checks = inlineChecks();
  for (const kind of kinds) {
    checks[kind] = async () => {
      throw new CheckFailed("Worker terminated due to reaching memory limit");
    };
  }
  return checks;
}

test("a page too heavy to check is too large for live editing", async () => {
  live = await liveFixture({ markdown: "Text", createCollabServer, checks: failing("open") });
  const anna = live.open({ grant: "herd_cg_a" });
  await until(() => anna.closes.includes(4413));
  assert.equal(live.api.saves.length, 0);
});

test("a state too heavy to check is not stored, and everyone is told", async () => {
  live = await liveFixture({ markdown: "Text", createCollabServer, checks: failing("readBack") });
  const anna = live.open({ grant: "herd_cg_a" });
  await synced(anna);
  const heard = [];
  anna.provider.on("stateless", ({ payload }) => heard.push(payload));
  const stored = live.api.saves.length;
  type(anna.doc, " mehr");
  await until(() => heard.includes(`${UNREPRESENTABLE}:unknown:`));
  assert.equal(live.api.saves.length, stored);
  assert.deepEqual(anna.closes, []);
});
