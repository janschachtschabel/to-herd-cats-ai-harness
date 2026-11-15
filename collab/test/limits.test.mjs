// One person cannot occupy live editing for everyone (review M2 R7, S6): connections
// are limited per login session (10), per page per session (3) and per person across
// all their logins (20, never more than a quarter of all), closed with 4429; a socket
// that has not completed the handshake within the timeout is closed (4408), and so is
// one that sends nothing for 15 minutes.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import WebSocket from "ws";
import { inlineChecks } from "../checks.mjs";
import { createCollabServer } from "../server.mjs";
import { ORIGIN, PAGE, liveFixture, synced, type, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const pageId = (n) => `${PAGE.slice(0, -2)}${String(n).padStart(2, "0")}`;
const anna = { cookie: "herd_session=token-a" };
const onPage = (n) => [{ ...anna, name: `page:${pageId(n)}` }, { page: pageId(n) }];

test("a login session holds at most 3 connections per page and 10 in all", async () => {
  live = await liveFixture({ createCollabServer });
  const first = [0, 1, 2].map(() => live.open(anna));
  await Promise.all(first.map(synced));
  const fourth = live.open(anna);
  await until(() => fourth.closes.includes(4429));
  // Other pages: 3 + 3 + 1 more, then the session is full.
  const more = [];
  for (const [page, count] of [
    [1, 3],
    [2, 3],
    [3, 1],
  ]) {
    for (let i = 0; i < count; i++) more.push(live.open(...onPage(page)));
  }
  await Promise.all(more.map(synced));
  const eleventh = live.open(...onPage(4));
  await until(() => eleventh.closes.includes(4429));
  // Someone else is not affected; a closed connection frees its place.
  const ben = live.open({ cookie: "herd_session=token-b" });
  await synced(ben);
  for (const c of [first[0], fourth, eleventh]) c.destroy(); // the refused ones retry
  await until(() => live.server.connections() === 10);
  const again = live.open(...onPage(5));
  await synced(again);
  assert.deepEqual(first[1].closes, []);
});

test("a socket that never completes the handshake is closed (4408)", async () => {
  live = await liveFixture({ createCollabServer, handshakeTimeoutMs: 200 });
  const url = `${live.base}/collab/${PAGE}?generation=0`;
  const idle = new WebSocket(url, { headers: { origin: ORIGIN, ...anna } });
  const closed = new Promise((resolve) => idle.on("close", (code) => resolve(code)));
  await new Promise((resolve) => idle.on("open", resolve));
  assert.equal(live.server.connections(), 1);
  assert.equal(await closed, 4408);
  await until(() => live.server.connections() === 0);
  // A browser that completes it stays.
  const c = live.open(anna);
  await synced(c);
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.deepEqual(c.closes, []);
});

test("a socket whose page is still being opened is not closed as idle (M4-1 P13)", async () => {
  // A page waits in the check queue behind a check that may run up to its time limit:
  // closing its socket meanwhile only made the browser come back later.
  const checks = inlineChecks();
  const open = checks.open;
  checks.open = async (markdown) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    return open(markdown);
  };
  live = await liveFixture({ createCollabServer, handshakeTimeoutMs: 200, checks });
  const c = live.open(anna);
  await until(() => c.provider.synced || c.closes.length > 0, 3000);
  assert.deepEqual(c.closes, []);
  assert.equal(c.provider.synced, true);
});

test("one person holds a limited number of connections across their logins", async () => {
  live = await liveFixture({ createCollabServer, maxPerPerson: 4 });
  const first = [0, 1, 2].map(() => live.open(anna));
  const second = live.open({ cookie: "herd_session=token-a2" });
  await Promise.all([...first, second].map(synced));
  const fifth = live.open(
    { cookie: "herd_session=token-a2", name: `page:${pageId(1)}` },
    {
      page: pageId(1),
    },
  );
  await until(() => fifth.closes.includes(4429));
  const ben = live.open({ cookie: "herd_session=token-b" });
  await synced(ben);
  fifth.destroy();
  first[0].destroy();
  await until(() => live.server.connections() === 4);
  const again = live.open({ cookie: "herd_session=token-a2" });
  await synced(again);
});

test("connections closed while being authenticated give their person's slot back (T7)", async () => {
  live = await liveFixture({ createCollabServer, maxPerPerson: 4 });
  live.api.authDelayMs = 30;
  for (let round = 0; round < 500 / 3; round++) {
    const calls = live.api.authCalls;
    const batch = [0, 1, 2].map(() => live.open(anna));
    await until(() => live.api.authCalls >= calls + 3);
    for (const c of batch) c.destroy(); // closed while the API is still answering
    await until(() => live.server.connections() === 0);
  }
  live.api.authDelayMs = 0;
  await new Promise((resolve) => setTimeout(resolve, 60)); // the last answers arrive
  const again = [0, 1, 2].map(() => live.open(anna));
  await until(() => again.every((c) => c.provider.synced));
  assert.deepEqual(
    again.flatMap((c) => c.closes),
    [],
  );
});

test("one person never holds more than a quarter of all connections", async () => {
  live = await liveFixture({ createCollabServer, maxConnections: 8 });
  const two = [0, 1].map(() => live.open(anna));
  await Promise.all(two.map(synced));
  const third = live.open(anna);
  await until(() => third.closes.includes(4429));
});

test("a connection that sends nothing for the idle timeout is closed", async () => {
  live = await liveFixture({ createCollabServer, idleTimeoutMs: 400, checkIntervalMs: 50 });
  const quiet = live.open(anna);
  const busy = live.open({ cookie: "herd_session=token-b" });
  await Promise.all([quiet, busy].map(synced));
  const typing = setInterval(() => type(busy.doc, "x"), 100);
  try {
    await until(() => quiet.closes.includes(4408));
    assert.deepEqual(busy.closes, []);
  } finally {
    clearInterval(typing);
  }
});
