// One person cannot occupy live editing for everyone (review M2 R7): connections are
// limited per login session (10) and per page per session (3), closed with 4429; a
// socket that has not completed the handshake within the timeout is closed (4408).
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import WebSocket from "ws";
import { createCollabServer } from "../server.mjs";
import { ORIGIN, PAGE, liveFixture, synced, until } from "./helpers.mjs";

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
