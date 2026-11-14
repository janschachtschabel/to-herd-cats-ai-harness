// Starts the app as it runs in production with role all (`python -m app.launch`: API,
// SPA from frontend/dist, collab process as its child) on a scratch database, and a
// local stand-in for an AI provider (the OpenAI stub of the backend tests, on the
// public port + 3: no real provider, no network), and returns the teardown that stops
// both and drops the database.
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = join(ROOT, "backend");
const DIST = join(ROOT, "frontend", "dist");
export const OWNER = { email: "anna@e2e.example", password: "e2e-password-123" };
/** The server key for `enc:` secrets (the AI connections' keys) in the scratch app. */
const SECRET_KEY = "e2e-secret-key-".padEnd(48, "k");

function psql(adminUrl, sql) {
  execFileSync("psql", [adminUrl, "-qc", sql], { stdio: "ignore" });
}

async function ready(url, deadline) {
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).status === 200) return;
    } catch {
      // not listening yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`not ready: ${url}`);
}

export default async function globalSetup() {
  if (!existsSync(join(DIST, "index.html"))) {
    throw new Error("frontend/dist is missing: run `npm run build` in frontend/ first");
  }
  const adminUrl =
    process.env.HERD_E2E_ADMIN_URL || "postgresql://herd:herd@localhost:5433/herd_test";
  const port = Number(process.env.HERD_E2E_PORT || 18080);
  const database = `herd_e2e_${process.pid}`;
  const url = new URL(adminUrl);
  psql(adminUrl, `DROP DATABASE IF EXISTS ${database}`);
  psql(adminUrl, `CREATE DATABASE ${database}`);
  const dataDir = mkdtempSync(join(tmpdir(), "herd-e2e-"));
  const app = spawn("uv", ["run", "--no-sync", "python", "-m", "app.launch"], {
    cwd: BACKEND,
    stdio: process.env.HERD_E2E_VERBOSE ? "inherit" : "ignore",
    env: {
      ...process.env,
      HERD_ROLE: "all",
      HERD_ENVIRONMENT: "development",
      HERD_DATABASE_URL: `postgresql+asyncpg://${url.username}:${url.password}@${url.host}/${database}`,
      HERD_PUBLIC_PORT: String(port),
      HERD_INTERNAL_PORT: String(port + 1),
      HERD_COLLAB_PORT: String(port + 2),
      HERD_COLLAB_URL: `ws://127.0.0.1:${port + 2}`,
      HERD_INTERNAL_TOKEN: "e2e-".padEnd(48, "x"),
      HERD_BOOTSTRAP_ADMIN_EMAIL: OWNER.email,
      HERD_BOOTSTRAP_ADMIN_PASSWORD: OWNER.password,
      HERD_STATIC_DIR: DIST,
      HERD_DATA_DIR: dataDir,
      HERD_LOG_FORMAT: "text",
      HERD_SECRET_KEY: SECRET_KEY,
    },
  });
  const stub = spawn(
    "uv",
    ["run", "--no-sync", "python", "-m", "tests.support.openai_stub", "--port", String(port + 3)],
    { cwd: BACKEND, stdio: process.env.HERD_E2E_VERBOSE ? "inherit" : "ignore" },
  );
  const exited = new Promise((resolve) => app.once("exit", resolve));
  const stubExited = new Promise((resolve) => stub.once("exit", resolve));
  const teardown = async () => {
    if (app.exitCode === null) app.kill("SIGTERM");
    if (stub.exitCode === null) stub.kill("SIGTERM");
    await exited;
    await stubExited;
    psql(adminUrl, `DROP DATABASE IF EXISTS ${database} WITH (FORCE)`);
    rmSync(dataDir, { recursive: true, force: true });
  };
  try {
    const deadline = Date.now() + 90_000;
    await ready(`http://127.0.0.1:${port + 1}/ready`, deadline);
    await ready(`http://127.0.0.1:${port + 2}/health`, deadline);
    await ready(`http://127.0.0.1:${port + 3}/_stub/log`, deadline);
  } catch (error) {
    await teardown();
    throw error;
  }
  return teardown;
}
