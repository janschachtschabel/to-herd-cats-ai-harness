// Starts the app as it runs in production with role all (`python -m app.launch`: API,
// SPA from frontend/dist, worker, collab process as its child) on a scratch database,
// and a local stand-in for an AI provider (the OpenAI stub of the backend tests, on the
// public port + 3: no real provider, no network), and returns the teardown that stops
// both and drops the database.
//
// Restarting the worker (plan M6 task 13): in role all the worker runs in the app's
// process, so a test restarts the app. The app is started as a process group of its
// own (uv, python and the collab child); a control route on the public port + 4,
// `POST /restart-app`, kills that group with SIGKILL (a crash: no orderly stop, the
// runs in progress keep their lease), starts the app again on the same database and
// answers once it is ready (`restartApp()` in tests/ai-helpers.mjs). The runs' lease is
// 5 s here (HERD_RUN_LEASE_SECONDS), so the new worker takes a crashed run up soon.
//
// Moving the app's time (plan M7 task 10): the app starts through
// `python -m tests.support.e2e_clock`, which makes the clock that schedules
// (`app.core.clock.SYSTEM_CLOCK`) the system time plus an offset read from a file in
// the scratch data directory, then runs `app.launch` as usual. `POST /clock` on the
// control port with `{"offset_seconds": n}` writes that offset (`GET /clock` reads it),
// so a term comes due at once instead of in minutes or days (`clockTo()` in
// tests/automations-helpers.mjs). The launcher lives in the backend's test tree,
// which the image never contains; nothing under `app/` knows it.
//
// MCP (plan M8 task 12): the MCP stub (public port + 5, endpoint `/mcp`) and the OAuth
// stub (public port + 6) of the backend tests run as processes over https for the name
// `localhost`, with a certificate made here for the run. The app dials external servers
// and OAuth endpoints over https only and private hosts only when the operator lists
// them, so it gets HERD_MCP_ALLOWED_HOSTS=localhost and trusts the certificate through
// SSL_CERT_FILE (its outbound clients read it; nothing else it calls uses TLS here).
// HERD_PUBLIC_URL makes the OAuth redirect address; HERD_MCP_CATALOG_DIR holds an
// operator catalogue file whose entry points at the MCP stub (and one broken file).
// The browser accepts the stubs' certificate per context (`ignoreHTTPSErrors`), as do
// the tests' requests to their control routes (tests/mcp-helpers.mjs).
//
// Sign-in (plan M9 task 5): the OIDC stub of the backend tests (public port + 7) runs
// the same way over https for `localhost`; HERD_OIDC_ALLOWED_HOSTS=localhost lets the
// app reach it, and HERD_OIDC_STUB_SECRET is the client secret a provider may name as
// `env:` (tests/oidc-helpers.mjs).
import { execFileSync, spawn } from "node:child_process";
import { createServer } from "node:http";
import { get as httpsGet } from "node:https";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
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

/** Answers once `url` (https, trusting only `ca`) answers 200. */
async function readyTls(url, ca, deadline) {
  const once = () =>
    new Promise((resolve) => {
      const request = httpsGet(url, { ca }, (response) => {
        response.resume();
        resolve(response.statusCode === 200);
      });
      request.on("error", () => resolve(false));
    });
  while (Date.now() < deadline) {
    if (await once()) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`not ready: ${url}`);
}

/** A certificate for `localhost` (its own CA) and its key, in `directory`. */
function stubCertificate(directory) {
  const script = [
    "import sys",
    "from pathlib import Path",
    "from tests.support.openai_stub import self_signed",
    "self_signed(Path(sys.argv[1]), ['localhost'])",
  ].join("\n");
  execFileSync("uv", ["run", "--no-sync", "python", "-c", script, directory], { cwd: BACKEND });
  return { cert: join(directory, "stub-cert.pem"), key: join(directory, "stub-key.pem") };
}

/** An operator catalogue: one entry for the MCP stub, one file that does not load. */
function operatorCatalogue(directory, mcpUrl) {
  mkdirSync(directory);
  const entry = [
    "id: e2e-tracker",
    "name: Tracker",
    'description: {de: "Der Tracker der Browser-Tests.", en: "The browser tests\' tracker."}',
    `url: "${mcpUrl}"`,
    "data_location: local",
    "connector_scopes: [none, shared, personal]",
    "auth:",
    "  - kind: bearer",
    "tools:",
    "  search_issues: read",
    "  create_issue: write",
    "",
  ].join("\n");
  writeFileSync(join(directory, "tracker.yaml"), entry);
  writeFileSync(join(directory, "broken.yaml"), "id: broken\nname: Kaputt\nunknown_field: 1\n");
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
  const clockFile = join(dataDir, "clock-offset");
  const tls = stubCertificate(dataDir);
  const mcpUrl = `https://localhost:${port + 5}/mcp`;
  const catalogDir = join(dataDir, "mcp-catalog");
  operatorCatalogue(catalogDir, mcpUrl);
  const databaseUrl = `postgresql+asyncpg://${url.username}:${url.password}@${url.host}/${database}`;
  // For what the tests make through the backend itself (`seedProposal`): the workers
  // inherit this process's environment.
  process.env.HERD_E2E_DATABASE_URL = databaseUrl;
  const appEnv = {
    ...process.env,
    HERD_ROLE: "all",
    HERD_ENVIRONMENT: "development",
    HERD_DATABASE_URL: databaseUrl,
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
    HERD_RUN_LEASE_SECONDS: "5",
    HERD_E2E_CLOCK_FILE: clockFile,
    HERD_PUBLIC_URL: `http://127.0.0.1:${port}`,
    HERD_MCP_ALLOWED_HOSTS: "localhost",
    HERD_MCP_CATALOG_DIR: catalogDir,
    HERD_OIDC_ALLOWED_HOSTS: "localhost",
    HERD_OIDC_STUB_SECRET: "oidc-SECRET-value-7",
    SSL_CERT_FILE: tls.cert,
  };
  const startApp = () => {
    const child = spawn("uv", ["run", "--no-sync", "python", "-m", "tests.support.e2e_clock"], {
      cwd: BACKEND,
      stdio: process.env.HERD_E2E_VERBOSE ? "inherit" : "ignore",
      env: appEnv,
      detached: true, // a process group of its own: the restart kills all of it
    });
    return { child, exited: new Promise((resolve) => child.once("exit", resolve)) };
  };
  const killGroup = (child, signal) => {
    try {
      process.kill(-child.pid, signal);
    } catch {
      // already gone
    }
  };
  let app = startApp();
  // Should this process end without the teardown, the app's group goes with it.
  const orphanGuard = () => killGroup(app.child, "SIGKILL");
  process.once("exit", orphanGuard);
  const appReady = async () => {
    const deadline = Date.now() + 90_000;
    await ready(`http://127.0.0.1:${port + 1}/ready`, deadline);
    await ready(`http://127.0.0.1:${port + 2}/health`, deadline);
  };
  let restarting = Promise.resolve();
  const offset = () => (existsSync(clockFile) ? Number(readFileSync(clockFile, "utf8")) : 0);
  const clock = (request, response) => {
    const answer = () => {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ offset_seconds: offset() }));
    };
    if (request.method === "GET") return answer();
    let body = "";
    request.on("data", (chunk) => (body += chunk));
    request.on("end", () => {
      const seconds = Number(JSON.parse(body || "{}").offset_seconds);
      if (!Number.isFinite(seconds)) return response.writeHead(400).end();
      writeFileSync(`${clockFile}.next`, String(seconds));
      renameSync(`${clockFile}.next`, clockFile); // the app never reads half a number
      answer();
    });
  };
  const control = createServer((request, response) => {
    if (request.url === "/clock" && ["GET", "POST"].includes(request.method)) {
      clock(request, response);
      return;
    }
    if (request.method !== "POST" || request.url !== "/restart-app") {
      response.writeHead(404).end();
      return;
    }
    restarting = restarting.then(async () => {
      try {
        killGroup(app.child, "SIGKILL");
        await app.exited;
        app = startApp();
        await appReady();
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify({ pid: app.child.pid }));
      } catch (error) {
        response.writeHead(500).end(String(error));
      }
    });
  });
  await new Promise((resolve) => control.listen(port + 4, "127.0.0.1", resolve));
  const stub = spawn(
    "uv",
    ["run", "--no-sync", "python", "-m", "tests.support.openai_stub", "--port", String(port + 3)],
    { cwd: BACKEND, stdio: process.env.HERD_E2E_VERBOSE ? "inherit" : "ignore" },
  );
  const stubExited = new Promise((resolve) => stub.once("exit", resolve));
  const tlsStub = (module, stubPort) => {
    const child = spawn(
      "uv",
      [
        "run",
        "--no-sync",
        "python",
        "-m",
        module,
        "--port",
        String(stubPort),
        "--certfile",
        tls.cert,
        "--keyfile",
        tls.key,
        "--name",
        "localhost",
      ],
      { cwd: BACKEND, stdio: process.env.HERD_E2E_VERBOSE ? "inherit" : "ignore" },
    );
    return { child, exited: new Promise((resolve) => child.once("exit", resolve)) };
  };
  const mcpStub = tlsStub("tests.support.mcp_stub", port + 5);
  const oauthStub = tlsStub("tests.support.oauth_stub", port + 6);
  const oidcStub = tlsStub("tests.support.oidc_stub", port + 7);
  const teardown = async () => {
    control.closeAllConnections();
    await new Promise((resolve) => control.close(resolve));
    await restarting;
    if (app.child.exitCode === null) killGroup(app.child, "SIGTERM");
    if (stub.exitCode === null) stub.kill("SIGTERM");
    for (const { child } of [mcpStub, oauthStub, oidcStub]) {
      if (child.exitCode === null) child.kill("SIGTERM");
    }
    await app.exited;
    await stubExited;
    await mcpStub.exited;
    await oauthStub.exited;
    await oidcStub.exited;
    process.removeListener("exit", orphanGuard);
    psql(adminUrl, `DROP DATABASE IF EXISTS ${database} WITH (FORCE)`);
    rmSync(dataDir, { recursive: true, force: true });
  };
  try {
    await appReady();
    await ready(`http://127.0.0.1:${port + 3}/_stub/log`, Date.now() + 90_000);
    const ca = readFileSync(tls.cert);
    await readyTls(`https://localhost:${port + 5}/_stub/log`, ca, Date.now() + 90_000);
    await readyTls(`https://localhost:${port + 6}/_stub/log`, ca, Date.now() + 90_000);
    await readyTls(`https://localhost:${port + 7}/_stub/log`, ca, Date.now() + 90_000);
  } catch (error) {
    await teardown();
    throw error;
  }
  return teardown;
}
