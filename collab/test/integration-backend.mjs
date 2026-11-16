// The real API for the integration tests (`npm run test:integration`): `python -m
// app.launch` with HERD_ROLE=all (API, worker and this collab process as its child, the
// one instance at 127.0.0.1) on a scratch database, plus helpers for its REST API,
// browser-like clients through the relay `/collab`, and further collab processes of
// their own (`spawnCollab`, role collab, plan M9 task 15). Needs PostgreSQL, uv and psql;
// runs only with HERD_COLLAB_INTEGRATION=1.
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { client, until } from "./helpers.mjs";

export const enabled = process.env.HERD_COLLAB_INTEGRATION === "1";
export const INTERNAL_TOKEN = "it-".padEnd(48, "x");
export const PASSWORD = "integration-pw-123";
const ADMIN_URL =
  process.env.HERD_IT_ADMIN_URL ?? "postgresql://herd:herd@localhost:5433/herd_test";
const HERE = dirname(fileURLToPath(import.meta.url));
const BACKEND = join(HERE, "..", "..", "backend");
const SERVER = join(HERE, "..", "server.mjs");

export function freePort() {
  return new Promise((resolve) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function psqlOn(url, sql) {
  return execFileSync("psql", [url, "-qAtc", sql], { encoding: "utf8" }).trim();
}

function exited(child) {
  return child.exitCode !== null || child.signalCode !== null
    ? Promise.resolve()
    : new Promise((resolve) => child.once("exit", resolve));
}

async function healthy(url) {
  try {
    return (await fetch(url)).status === 200;
  } catch {
    return false;
  }
}

export async function startBackend() {
  const database = `herd_collab_it_${process.pid}`;
  psqlOn(ADMIN_URL, `DROP DATABASE IF EXISTS ${database}`);
  psqlOn(ADMIN_URL, `CREATE DATABASE ${database}`);
  const dataDir = mkdtempSync(join(tmpdir(), "herd-collab-it-"));
  const [publicPort, internalPort, collabPort] = [
    await freePort(),
    await freePort(),
    await freePort(),
  ];
  const url = new URL(ADMIN_URL);
  const databaseUrl = `postgresql://${url.username}:${url.password}@${url.host}/${database}`;
  const base = `http://127.0.0.1:${publicPort}`;
  const internalBase = `http://127.0.0.1:${internalPort}`;
  const verbose = process.env.HERD_IT_VERBOSE ? "inherit" : "ignore";
  const backend = spawn("uv", ["run", "--no-sync", "python", "-m", "app.launch"], {
    cwd: BACKEND,
    stdio: verbose,
    env: {
      ...process.env,
      HERD_ROLE: "all",
      HERD_ENVIRONMENT: "development",
      HERD_DATABASE_URL: `postgresql+asyncpg://${url.username}:${url.password}@${url.host}/${database}`,
      HERD_PUBLIC_PORT: String(publicPort),
      HERD_INTERNAL_PORT: String(internalPort),
      HERD_COLLAB_PORT: String(collabPort),
      HERD_INTERNAL_TOKEN: INTERNAL_TOKEN,
      HERD_BOOTSTRAP_ADMIN_EMAIL: "owner@it.example",
      HERD_BOOTSTRAP_ADMIN_PASSWORD: PASSWORD,
      HERD_DATA_DIR: dataDir,
      HERD_LOG_FORMAT: "text",
    },
  });
  await until(
    async () =>
      (await healthy(`${internalBase}/ready`)) &&
      (await healthy(`http://127.0.0.1:${collabPort}/health`)),
    60_000,
  );
  const clients = [];
  const collabs = [];

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

  return {
    base,
    wsBase: `ws://127.0.0.1:${publicPort}`,
    collabBase: `127.0.0.1:${collabPort}`,
    internalBase,
    api,
    /** One SQL statement on the scratch database; its output. */
    psql: (sql) => psqlOn(databaseUrl, sql),
    async login(email) {
      const r = await api("/api/auth/login", {
        method: "POST",
        body: { email, password: PASSWORD },
      });
      assert.equal(r.status, 200, JSON.stringify(r.body));
      const cookie = r.headers.get("set-cookie").split(";")[0];
      return { cookie, user: r.body.user };
    },
    /** A browser on the page, through the relay. */
    open(cookie, pageId, generation) {
      const c = client(`ws://127.0.0.1:${publicPort}/collab/${pageId}?generation=${generation}`, {
        cookie,
        origin: base,
        name: `page:${pageId}`,
      });
      clients.push(c);
      return c;
    },
    async content(cookie, pageId) {
      return (await api(`/api/pages/${pageId}`, { cookie })).body;
    },
    /** Another collab process (role collab) announcing itself at its own port. */
    async spawnCollab() {
      const port = await freePort();
      const child = spawn(process.execPath, [SERVER], {
        stdio: verbose,
        env: {
          PATH: process.env.PATH,
          HERD_ROLE: "collab",
          HERD_INTERNAL_TOKEN: INTERNAL_TOKEN,
          HERD_COLLAB_API_URL: internalBase,
          HERD_COLLAB_HOST: "127.0.0.1",
          HERD_COLLAB_PORT: String(port),
          HERD_COLLAB_ADVERTISE_URL: `ws://127.0.0.1:${port}`,
        },
      });
      const collab = {
        child,
        url: `ws://127.0.0.1:${port}`,
        async documents() {
          const text = await (await fetch(`http://127.0.0.1:${port}/metrics`)).text();
          return Number(/^herd_collab_documents (\d+)$/m.exec(text)?.[1] ?? NaN);
        },
        /** SIGTERM: it drains (saves, releases its pages) and exits. */
        async stop() {
          child.kill("SIGTERM");
          await exited(child);
        },
      };
      collabs.push(collab);
      await until(() => healthy(`http://127.0.0.1:${port}/health`), 15_000);
      return collab;
    },
    async stop() {
      for (const c of clients) c.destroy();
      for (const { child } of collabs) child.kill("SIGKILL");
      await Promise.all(collabs.map(({ child }) => exited(child)));
      backend.kill("SIGTERM");
      await exited(backend);
      psqlOn(ADMIN_URL, `DROP DATABASE IF EXISTS ${database} WITH (FORCE)`);
      rmSync(dataDir, { recursive: true, force: true });
    },
  };
}
