// A check has a time limit (review M4-1 P13): a page of 40,000 emphasis runs in one
// paragraph held the only check worker for 83 s. Past the limit the worker is ended and
// replaced; only the check it ran fails (`CheckTimedOut`), the waiting ones run on the
// fresh worker. Opening such a page is "too large" (4413, nothing stored); a state that
// takes too long to check is not stored and everyone is told why ("timeout").
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { CheckFailed, CheckTimedOut, createChecks, inlineChecks } from "../checks.mjs";
import { UNREPRESENTABLE } from "../protocol.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, type, until } from "./helpers.mjs";

// The reviewer's page shape: emphasis runs in one paragraph (micromark resolves them in
// time quadratic in their number). 8,000 take seconds, far over a limit of 300 ms.
const HEAVY = "*a* ".repeat(8000) + "\n";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

test("a check over the time limit fails alone; the waiting ones run on a fresh worker", async () => {
  const checks = createChecks({ timeoutMs: 300 });
  try {
    const started = Date.now();
    const heavy = checks.open(HEAVY);
    const waiting = ["Eins\n", "Zwei\n"].map((markdown) => checks.open(markdown));
    await assert.rejects(heavy, (error) => error instanceof CheckTimedOut);
    for (const answer of await Promise.all(waiting)) assert.equal(answer.safe, true);
    // The small pages waited at most the limit and a fresh worker's start.
    assert.ok(Date.now() - started < 300 + 3000, `${Date.now() - started} ms`);
    assert.equal(checks.restarts, 1);
    // Not run again: answered at once.
    const again = Date.now();
    await assert.rejects(checks.open(HEAVY), CheckTimedOut);
    assert.ok(Date.now() - again < 100);
  } finally {
    await checks.close();
  }
});

test("a timed-out check is a failed check (the same path as out of memory)", () => {
  assert.ok(new CheckTimedOut("x") instanceof CheckFailed);
});

/** Checks as on this thread, but the ones named run past the limit. */
function slow(...kinds) {
  const checks = inlineChecks();
  for (const kind of kinds) {
    checks[kind] = async () => {
      throw new CheckTimedOut("the check took longer than 10 s");
    };
  }
  return checks;
}

test("a page that takes too long to check is too large for live editing", async () => {
  live = await liveFixture({ markdown: "Text", createCollabServer, checks: slow("open") });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await until(() => anna.closes.includes(4413));
  assert.equal(live.api.saves.length, 0);
});

test("a state that takes too long to check is not stored; the notice says why", async () => {
  live = await liveFixture({ markdown: "Text", createCollabServer, checks: slow("readBack") });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  const heard = [];
  anna.provider.on("stateless", ({ payload }) => heard.push(payload));
  const stored = live.api.saves.length;
  type(anna.doc, " mehr");
  await until(() => heard.includes(`${UNREPRESENTABLE}:timeout:`));
  assert.equal(live.api.saves.length, stored);
  assert.deepEqual(anna.closes, []);
});

test("the reviewer's page holds another person's small page no longer than the limit", async () => {
  const limit = 1000;
  const small = "01a1d2d9-2de5-75db-9dc6-a6fa13072700";
  const checks = createChecks({ timeoutMs: limit });
  await checks.open("Start\n"); // the worker is ready: the heavy check starts at once
  live = await liveFixture({
    markdown: "*a* ".repeat(40_000) + "\n", // 160,001 characters, as in the review
    createCollabServer,
    checks,
  });
  live.api.pages[small] = "kleine Seite\n";
  const started = Date.now();
  const heavy = live.open({ cookie: "herd_session=token-a" });
  await new Promise((resolve) => setTimeout(resolve, 400)); // as in the review
  const ben = live.open({ cookie: "herd_session=token-b", name: `page:${small}` }, { page: small });
  await synced(ben);
  const waited = Date.now() - started;
  if (process.env.HERD_TEST_VERBOSE) console.log(`small page synced after ${waited} ms`);
  assert.ok(waited < limit + 2500, `the small page opened after ${waited} ms`);
  assert.deepEqual(ben.closes, []);
  await until(() => heavy.closes.includes(4413));
  assert.equal(live.api.saves.filter((save) => save.content_md.startsWith("*a*")).length, 0);
});
