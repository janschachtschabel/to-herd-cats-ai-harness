// The collab process against a fake internal API (plan M2 task 9).
import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import WebSocket from "ws";
import { createCollabServer, originAllowed } from "../server.mjs";
import { ORIGIN, PAGE, client, fakeApi, synced, type, until } from "./helpers.mjs";

const TOKEN = "i".repeat(40);
let api;
let server;
let base;
const clients = [];

beforeEach(async () => {
  api = await fakeApi();
  server = createCollabServer({
    apiUrl: api.url,
    token: TOKEN,
    publicUrl: ORIGIN,
    checkIntervalMs: 100,
    debounceMs: 50,
    maxDebounceMs: 200,
    retryMs: 50,
    log: () => {},
  });
  const address = await server.listen(0, "127.0.0.1");
  base = `ws://127.0.0.1:${address.port}`;
});

afterEach(async () => {
  for (const c of clients.splice(0)) c.destroy();
  await server.close();
  await api.close();
});

function open(options, { generation = 0, page = PAGE } = {}) {
  const c = client(`${base}/collab/${page}?generation=${generation}`, options);
  clients.push(c);
  return c;
}

function refusedWith(url, headers) {
  return new Promise((resolve) => {
    const ws = new WebSocket(url, { headers });
    ws.on("unexpected-response", (_request, response) => resolve(response.statusCode));
    ws.on("open", () => resolve("open"));
    ws.on("error", () => {});
  });
}

test("health answers 200", async () => {
  const response = await fetch(`${base.replace("ws", "http")}/health`);
  assert.equal(response.status, 200);
});

test("rejects connection without cookie", async () => {
  const c = open({});
  await until(() => c.closes.includes(4401));
  const stranger = open({ cookie: "herd_session=unknown" });
  await until(() => stranger.closes.includes(4401));
  assert.equal(api.saves.length, 0);
});

test("refuses foreign origins, other paths and bad generations at the handshake", async () => {
  const cookie = "herd_session=token-a";
  const url = `${base}/collab/${PAGE}?generation=0`;
  assert.equal(await refusedWith(url, { cookie, origin: "http://evil.example" }), 403);
  assert.equal(await refusedWith(url, { cookie }), 403);
  assert.equal(await refusedWith(`${base}/collab/x?generation=0`, { cookie, origin: ORIGIN }), 404);
  assert.equal(await refusedWith(`${base}/collab/${PAGE}`, { cookie, origin: ORIGIN }), 404);
  assert.equal(await refusedWith(`${base}/other`, { cookie, origin: ORIGIN }), 404);
});

test("a connection edits only the page of its URL", async () => {
  const c = open({
    cookie: "herd_session=token-a",
    name: "page:01a1d2d9-0000-75db-9dc6-a6fa1307273d",
  });
  await until(() => c.closes.includes(4403));
});

test("stores markdown after edit", async () => {
  const c = open({ cookie: "x=1; herd_session=token-a" });
  await synced(c);
  // Built from the Markdown and saved at once, unchanged.
  await until(() => api.saves.length === 1);
  assert.equal(api.saves[0].content_md, "# Start");
  assert.deepEqual(api.saves[0].editor_session_ids, ["session-a"]);
  type(c.doc, "Hallo Welt");
  await until(() => api.saves.length === 2);
  const save = api.saves[1];
  assert.equal(save.content_md, "# Start\n\nHallo Welt");
  assert.deepEqual(save.editor_session_ids, ["session-a"]);
  assert.equal(save.generation, 0);
  assert.equal(save.session_key, api.saves[0].session_key);
  assert.ok(Buffer.from(save.ydoc_b64, "base64").length > 0);
  assert.ok(api.tokens.every((t) => t === TOKEN));
});

test("closes with 4409 when api answers generation_ended", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  const b = open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(a), synced(b)]);
  await until(() => api.saves.length === 1);
  api.saveAnswer = () => [
    409,
    { error: { code: "collab.generation_ended", details: { generation: 1 } } },
  ];
  type(a.doc, "veraltet");
  await until(() => a.closes.includes(4409) && b.closes.includes(4409));
});

test("a stale browser document is refused", async () => {
  api.generation = 1;
  const c = open({ cookie: "herd_session=token-a" }, { generation: 0 });
  await until(() => c.closes.includes(4409));
  assert.equal(api.saves.length, 0);
});

test("ends every connection when the check reports a new generation", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  await synced(a);
  api.checkAnswer = () => [
    200,
    { generation_ok: false, generation: 1, revoked_session_ids: [], revoked_user_ids: [] },
  ];
  await until(() => a.closes.includes(4409));
});

test("closes revoked user with 4403", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  const b = open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(a), synced(b)]);
  api.checkAnswer = () => [
    200,
    { generation_ok: true, generation: 0, revoked_session_ids: [], revoked_user_ids: ["user-b"] },
  ];
  await until(() => b.closes.includes(4403));
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.ok(!a.closes.length, "Anna did nothing wrong and keeps editing");
  api.checkAnswer = () => [
    200,
    { generation_ok: true, generation: 0, revoked_session_ids: [], revoked_user_ids: [] },
  ];
  type(a.doc, "weiter");
  await until(() => api.saves.some((s) => s.content_md.includes("weiter")));
});

/** The API's check: session-b is revoked; unsaved edits of it end the generation. */
function revokedB(body) {
  const ended = body.unsaved_session_ids.includes("session-b");
  return [
    200,
    {
      generation_ok: !ended,
      generation: ended ? 1 : 0,
      revoked_session_ids: ["session-b"],
      revoked_user_ids: ["user-b"],
    },
  ];
}

test("a revoked editor's refused save ends the generation; nothing of it is saved", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  const b = open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(a), synced(b)]);
  await until(() => api.saves.length === 1);
  api.saveAnswer = (body) =>
    body.editor_session_ids.includes("session-b")
      ? [
          403,
          {
            error: {
              code: "collab.editors_revoked",
              details: { revoked_session_ids: ["session-b"], revoked_user_ids: ["user-b"] },
            },
          },
        ]
      : [200, { generation: 0, version: 3 }];
  api.checkAnswer = revokedB;
  type(b.doc, "verboten");
  await until(() => b.closes.includes(4403) && a.closes.includes(4409));
  assert.ok(api.checks.some((c) => c.unsaved_session_ids.includes("session-b")));
  assert.ok(
    api.checks.every((c) => c.session_ids.includes("session-a")),
    "names the page's org",
  );
  assert.ok(
    !api.saves.some(
      (s) => s.content_md.includes("verboten") && !s.editor_session_ids.includes("session-b"),
    ),
  );
});

test("a check that finds a revoked editor's unsaved edits ends the generation", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  const b = open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(a), synced(b)]);
  await until(() => api.saves.length === 1);
  api.saveAnswer = () => [503, {}]; // the save does not get through: b's edit stays unsaved
  type(b.doc, "verboten");
  await new Promise((resolve) => setTimeout(resolve, 150));
  api.checkAnswer = revokedB;
  await until(() => b.closes.includes(4403) && a.closes.includes(4409));
  assert.equal(a.closes[0], 4409);
});

test("while the generation cannot be ended, the document takes no one", async () => {
  const a = open({ cookie: "herd_session=token-a" });
  const b = open({ cookie: "herd_session=token-b" });
  await Promise.all([synced(a), synced(b)]);
  await until(() => api.saves.length === 1);
  api.saveAnswer = () => [
    403,
    {
      error: {
        code: "collab.editors_revoked",
        details: { revoked_session_ids: ["session-b"], revoked_user_ids: ["user-b"] },
      },
    },
  ];
  api.checkAnswer = () => [503, {}];
  type(b.doc, "verboten");
  await until(() => api.checks.length > 0);
  const late = open({ cookie: "herd_session=token-a" });
  await until(() => late.closes.includes(1013));
  assert.ok(!late.provider.synced);
  api.checkAnswer = revokedB;
  await until(() => a.closes.includes(4409) && b.closes.includes(4403));
});

test("origin check without HERD_PUBLIC_URL compares hosts", () => {
  assert.ok(originAllowed({ origin: "https://wiki.example", host: "wiki.example" }, null));
  assert.ok(
    originAllowed(
      {
        origin: "https://wiki.example",
        host: "127.0.0.1:1234",
        "x-forwarded-host": "wiki.example",
      },
      null,
    ),
  );
  assert.ok(!originAllowed({ origin: "https://evil.example", host: "wiki.example" }, null));
  assert.ok(!originAllowed({ host: "wiki.example" }, null));
  assert.ok(!originAllowed({ origin: "https://wiki.example:8443", host: "wiki.example" }, null));
  assert.ok(!originAllowed({ origin: "http://wiki.example" }, "https://wiki.example"));
});

test("presence colours carry white text at WCAG AA contrast", async () => {
  const { colorFor } = await import("../live.mjs");
  const luminance = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  };
  const colours = new Set(Array.from({ length: 200 }, (_, i) => colorFor(`user-${i}`)));
  assert.ok(colours.size > 3);
  for (const colour of colours) {
    assert.ok(1.05 / (luminance(colour) + 0.05) >= 4.5, colour);
  }
});
