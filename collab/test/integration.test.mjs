// End to end: the real API (`python -m app.launch`, HERD_ROLE=all, which starts this
// collab process as its child) on a scratch database, two browser-like Yjs clients
// through the relay `/collab`. Covers the review focus "stale live session" and
// "rights revocation". Needs PostgreSQL, uv and psql; runs only with
// HERD_COLLAB_INTEGRATION=1 (`npm run test:integration`).
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { yDocToMarkdown } from "../markdown.mjs";
import { client, synced, type, until } from "./helpers.mjs";

const enabled = process.env.HERD_COLLAB_INTEGRATION === "1";
const ADMIN_URL =
  process.env.HERD_IT_ADMIN_URL ?? "postgresql://herd:herd@localhost:5433/herd_test";
const BACKEND = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "backend");
const PASSWORD = "integration-pw-123";
const database = `herd_collab_it_${process.pid}`;
let backend;
let dataDir;
let base;
let wsBase;
const clients = [];

function freePort() {
  return new Promise((resolve) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function psql(sql) {
  execFileSync("psql", [ADMIN_URL, "-qc", sql], { stdio: "ignore" });
}

async function api(path, { method = "GET", cookie, body } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "herd",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  return {
    status: response.status,
    body: text ? JSON.parse(text) : null,
    headers: response.headers,
  };
}

async function login(email) {
  const r = await api("/api/auth/login", { method: "POST", body: { email, password: PASSWORD } });
  assert.equal(r.status, 200, JSON.stringify(r.body));
  const cookie = r.headers.get("set-cookie").split(";")[0];
  return { cookie, user: r.body.user };
}

function open(cookie, pageId, generation) {
  const c = client(`${wsBase}/collab/${pageId}?generation=${generation}`, {
    cookie,
    origin: base,
    name: `page:${pageId}`,
  });
  clients.push(c);
  return c;
}

async function content(cookie, pageId) {
  return (await api(`/api/pages/${pageId}`, { cookie })).body;
}

before(async () => {
  if (!enabled) return;
  psql(`DROP DATABASE IF EXISTS ${database}`);
  psql(`CREATE DATABASE ${database}`);
  dataDir = mkdtempSync(join(tmpdir(), "herd-collab-it-"));
  const [publicPort, internalPort, collabPort] = [
    await freePort(),
    await freePort(),
    await freePort(),
  ];
  const url = new URL(ADMIN_URL);
  base = `http://127.0.0.1:${publicPort}`;
  wsBase = `ws://127.0.0.1:${publicPort}`;
  backend = spawn("uv", ["run", "--no-sync", "python", "-m", "app.launch"], {
    cwd: BACKEND,
    stdio: process.env.HERD_IT_VERBOSE ? "inherit" : "ignore",
    env: {
      ...process.env,
      HERD_ROLE: "all",
      HERD_ENVIRONMENT: "development",
      HERD_DATABASE_URL: `postgresql+asyncpg://${url.username}:${url.password}@${url.host}/${database}`,
      HERD_PUBLIC_PORT: String(publicPort),
      HERD_INTERNAL_PORT: String(internalPort),
      HERD_COLLAB_PORT: String(collabPort),
      HERD_COLLAB_URL: `ws://127.0.0.1:${collabPort}`,
      HERD_INTERNAL_TOKEN: "it-".padEnd(48, "x"),
      HERD_BOOTSTRAP_ADMIN_EMAIL: "owner@it.example",
      HERD_BOOTSTRAP_ADMIN_PASSWORD: PASSWORD,
      HERD_DATA_DIR: dataDir,
      HERD_LOG_FORMAT: "text",
    },
  });
  await until(async () => {
    try {
      const ready = await fetch(`http://127.0.0.1:${internalPort}/ready`);
      const live = await fetch(`http://127.0.0.1:${collabPort}/health`);
      return ready.status === 200 && live.status === 200;
    } catch {
      return false;
    }
  }, 60_000);
});

after(async () => {
  if (!enabled) return;
  for (const c of clients) c.destroy();
  if (backend) {
    backend.kill("SIGTERM");
    await new Promise((resolve) => backend.once("exit", resolve));
  }
  psql(`DROP DATABASE IF EXISTS ${database} WITH (FORCE)`);
  rmSync(dataDir, { recursive: true, force: true });
});

test(
  "two browsers edit live; a Markdown save and a revoked right end it cleanly",
  { skip: !enabled, timeout: 180_000 },
  async () => {
    const owner = await login("owner@it.example");
    const created = await api("/api/admin/users", {
      method: "POST",
      cookie: owner.cookie,
      body: { email: "member@it.example", name: "Mitglied", password: PASSWORD },
    });
    assert.equal(created.status, 201, JSON.stringify(created.body));
    const member = await login("member@it.example");
    const space = (
      await api("/api/spaces", {
        method: "POST",
        cookie: owner.cookie,
        body: { name: "Live", kind: "team" },
      })
    ).body;
    const role = (r) => ({ member_type: "user", member_id: member.user.id, role: r });
    await api(`/api/spaces/${space.id}/members`, {
      method: "PUT",
      cookie: owner.cookie,
      body: role("editor"),
    });
    let page = (
      await api(`/api/spaces/${space.id}/pages`, {
        method: "POST",
        cookie: owner.cookie,
        body: { title: "Live", content_md: "# Start" },
      })
    ).body;
    page = (
      await api(`/api/pages/${page.id}/publish`, {
        method: "POST",
        cookie: owner.cookie,
        body: { version: page.version },
      })
    ).body;

    // Two browsers, one document.
    const a = open(owner.cookie, page.id, 0);
    const b = open(member.cookie, page.id, 0);
    await Promise.all([synced(a), synced(b)]);
    assert.equal(yDocToMarkdown(a.doc), "# Start");
    type(a.doc, "Hallo von A");
    await until(() => yDocToMarkdown(b.doc).includes("Hallo von A"));
    type(b.doc, " und B");
    await until(
      async () =>
        (await content(owner.cookie, page.id)).content_md === "# Start\n\nHallo von A und B",
      15_000,
    );
    const versions = (await api(`/api/pages/${page.id}/versions`, { cookie: owner.cookie })).body
      .items;
    assert.ok(
      versions.some((v) => v.source === "collab"),
      JSON.stringify(versions),
    );

    // Rights revocation: Mitglied becomes a viewer while typing.
    await api(`/api/spaces/${space.id}/members`, {
      method: "PUT",
      cookie: owner.cookie,
      body: role("viewer"),
    });
    type(b.doc, " nach dem Entzug");
    await until(() => b.closes.includes(4403), 15_000);
    // The unsaved state held B's edit: the generation ends, so A's browser, which saw
    // the edit, cannot bring it back by reconnecting (its provider keeps trying).
    await until(() => a.closes.includes(4409), 15_000);
    await new Promise((resolve) => setTimeout(resolve, 4000));
    page = await content(owner.cookie, page.id);
    assert.equal(page.content_md, "# Start\n\nHallo von A und B");
    assert.equal(page.collab_generation, 1);
    a.destroy();
    b.destroy();

    // Stale live session: a Markdown save ends the generation.
    const live = open(owner.cookie, page.id, page.collab_generation);
    await synced(live);
    const patched = await api(`/api/pages/${page.id}`, {
      method: "PATCH",
      cookie: owner.cookie,
      body: { content_md: "# Markdown-Modus", version: page.version },
    });
    assert.equal(patched.status, 200, JSON.stringify(patched.body));
    type(live.doc, "alter Stand");
    await until(() => live.closes.includes(4409), 15_000);
    await new Promise((resolve) => setTimeout(resolve, 3000));
    page = await content(owner.cookie, page.id);
    assert.equal(page.content_md, "# Markdown-Modus");
    assert.equal(page.collab_generation, patched.body.collab_generation);
    live.destroy();
    // A browser still holding the old generation is refused at the relay, with a close
    // code it can read.
    const stale = open(owner.cookie, page.id, 0);
    await until(() => stale.closes.includes(4409), 15_000);
    assert.ok(!stale.provider.synced);
    stale.destroy();

    // The next session starts from the new Markdown. Logging out is not a revocation
    // (review M2 R2): what was typed is saved, only that connection closes (4401), the
    // other browser goes on in the same generation.
    const second = await login("owner@it.example");
    const fresh = open(owner.cookie, page.id, page.collab_generation);
    const other = open(second.cookie, page.id, page.collab_generation);
    await Promise.all([synced(fresh), synced(other)]);
    assert.equal(yDocToMarkdown(fresh.doc), "# Markdown-Modus");
    type(fresh.doc, "Letzter Satz vor dem Abmelden");
    await until(() => yDocToMarkdown(other.doc).includes("Letzter Satz"));
    assert.equal(
      (await api("/api/auth/logout", { method: "POST", cookie: owner.cookie })).status,
      204,
    );
    await until(() => fresh.closes.includes(4401), 15_000);
    await until(
      async () => (await content(second.cookie, page.id)).content_md.includes("Letzter Satz"),
      15_000,
    );
    type(other.doc, " und weiter");
    await until(
      async () => (await content(second.cookie, page.id)).content_md.includes("und weiter"),
      15_000,
    );
    const after = await content(second.cookie, page.id);
    assert.equal(after.collab_generation, page.collab_generation);
    assert.deepEqual(other.closes, []);
  },
);
