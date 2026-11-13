// The collab process (spec 9, E11): Hocuspocus behind one HTTP port.
//
// - `GET /health` answers 200 (the probe), `GET /metrics` the memory budget's numbers
//   (Prometheus text, `memory.mjs`); every other plain request 404.
// - WebSocket upgrades only on `/collab/<page id>?generation=<n>`, from an allowed
//   Origin (HERD_PUBLIC_URL, or the request's own host), with the session cookie, at
//   most 200 at a time, messages up to a whole live state (`size.mjs`; the API's relay
//   passes the same). The live rules are in `live.mjs`.
// - One login session (its cookie) holds at most HERD_COLLAB_MAX_PER_SESSION (10)
//   connections, at most HERD_COLLAB_MAX_PER_PAGE (3) of them on one page, and one
//   person across all their logins at most HERD_COLLAB_MAX_PER_PERSON (20), never more
//   than a quarter of all; more are closed with 4429 `too_many_connections`. A socket
//   that has not joined its document within 10 s is closed with 4408
//   `handshake_timeout` (while its page is still being opened, up to two check time
//   limits later), one that has sent nothing for HERD_COLLAB_IDLE_MINUTES (15)
//   with 4408 `idle_timeout`, so idle sockets cannot hold the global limit (review M2
//   R7, S6). An open editor sends its presence every 15 s.
//
// Settings (environment): HERD_INTERNAL_TOKEN (required), HERD_COLLAB_API_URL (the
// API's internal port, default http://127.0.0.1:9090), HERD_COLLAB_PORT (1234),
// HERD_COLLAB_HOST (127.0.0.1 with HERD_ROLE=all, else 0.0.0.0), HERD_PUBLIC_URL,
// HERD_SESSION_COOKIE_NAME (herd_session), HERD_COLLAB_CHECK_WORKERS (1: the threads
// that open and check pages, `checks.mjs`, each with a heap of at most 192 MB),
// HERD_COLLAB_CHECK_TIMEOUT_SECONDS (10: the time limit of one check; past it the
// worker is replaced, an open is "too large", a save is not stored),
// HERD_COLLAB_MEMORY_BUDGET_MB (400: what the loaded documents may hold by the estimate
// of `memory.mjs`; past it a page is refused with 4507 "busy").
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { Hocuspocus } from "@hocuspocus/server";
import { WebSocketServer } from "ws";
import { InternalApi } from "./api.mjs";
import { CHECK_TIMEOUT_MS, createChecks, inlineChecks } from "./checks.mjs";
import { liveExtension } from "./live.mjs";
import { DEFAULT_BUDGET_MB, memoryBudget, metricsText } from "./memory.mjs";
import { counter, logger, originAllowed, refuse } from "./admission.mjs";
import { CLOSE, readCookie } from "./protocol.mjs";

export { originAllowed };
import { MAX_MESSAGE_BYTES } from "./size.mjs";

const PAGE_PATH = /^\/collab\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

export function createCollabServer({
  apiUrl,
  token,
  publicUrl = null,
  cookieName = "herd_session",
  maxConnections = 200,
  maxPerSession = 10,
  maxPerPage = 3,
  maxPerPerson = 20,
  handshakeTimeoutMs = 10_000,
  idleTimeoutMs = 15 * 60_000,
  checkIntervalMs = 5000,
  debounceMs = 2000,
  maxDebounceMs = 10000,
  retryMs = 5000,
  log = logger({ service: "to-herd-cats-ai", component: "collab" }),
  maxStateBytes,
  maxMarkdownChars,
  measureEveryMs,
  checkWorkers = 1,
  checkHeapMb = 192,
  checkTimeoutMs = CHECK_TIMEOUT_MS,
  memoryBudgetBytes = DEFAULT_BUDGET_MB * 1024 * 1024,
  checks: givenChecks = null,
}) {
  const api = new InternalApi({ baseUrl: apiUrl, token });
  // Opening and saving a large page takes seconds of work: on worker threads, so that
  // every other live document goes on meanwhile (review M2 T9), each with a capped heap
  // (a page too heavy to check is too large for live editing). 0: on this thread.
  const checks =
    givenChecks ??
    (checkWorkers > 0
      ? createChecks({ workers: checkWorkers, heapMb: checkHeapMb, timeoutMs: checkTimeoutMs })
      : inlineChecks());
  const held = counter();
  const people = new WeakMap(); // socket -> the person's key, once authenticated
  const perPerson = Math.max(1, Math.min(maxPerPerson, Math.floor(maxConnections / 4)));
  const extension = liveExtension({
    api,
    cookieName,
    retryMs,
    log,
    checks,
    memory: memoryBudget({ budgetBytes: memoryBudgetBytes }),
    person(context, userId) {
      if (people.has(context.socket)) return true;
      // Closed while the API was answering: its close handler has run already and would
      // never give the slot back (review M2 T7).
      if (!sockets.has(context.socket)) return false;
      const key = `u:${userId}`;
      if (!held.take(key, perPerson)) return false;
      people.set(context.socket, key);
      return true;
    },
    maxStateBytes,
    maxMarkdownChars,
    measureEveryMs,
  });
  const hocuspocus = new Hocuspocus({
    name: "to-herd-cats-ai-collab",
    quiet: true,
    debounce: debounceMs,
    maxDebounce: maxDebounceMs,
    extensions: [extension],
  });
  const sockets = new Set();
  const lastHeard = new WeakMap(); // socket -> when its last message came
  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_MESSAGE_BYTES });
  let closing = null;

  const httpServer = createServer((request, response) => {
    if (request.method === "GET" && request.url === "/metrics") {
      response.writeHead(200, { "Content-Type": "text/plain; version=0.0.4; charset=utf-8" });
      return response.end(metricsText(extension.memory, hocuspocus.getDocumentsCount()));
    }
    const healthy = request.method === "GET" && request.url === "/health" && !closing;
    response.writeHead(healthy ? 200 : 404, { "Content-Type": "text/plain" });
    response.end(healthy ? "ok" : "not found");
  });

  httpServer.on("upgrade", (request, socket, head) => {
    const url = new URL(request.url ?? "/", "http://collab");
    const page = PAGE_PATH.exec(url.pathname);
    const generation = url.searchParams.get("generation") ?? "";
    if (closing) return refuse(socket, 503);
    if (!page || !/^\d{1,9}$/.test(generation)) return refuse(socket, 404);
    if (!originAllowed(request.headers, publicUrl)) return refuse(socket, 403);
    if (sockets.size >= maxConnections) return refuse(socket, 503);
    wss.handleUpgrade(request, socket, head, (ws) => {
      sockets.add(ws);
      // The login session by its cookie (hashed: no token is kept), before any message.
      const token = readCookie(request.headers.cookie, cookieName);
      const session = token && createHash("sha256").update(token).digest("base64");
      const keys = session ? [`s:${session}`, `p:${session}:${page[1]}`] : [];
      const taken = [];
      if (session) {
        if (held.take(keys[0], maxPerSession)) taken.push(keys[0]);
        if (taken.length === 1 && held.take(keys[1], maxPerPage)) taken.push(keys[1]);
      }
      const release = () => taken.splice(0).forEach((key) => held.give(key));
      if (taken.length !== keys.length) {
        release();
        ws.on("close", () => sockets.delete(ws));
        return ws.close(...CLOSE.tooMany);
      }
      // Not joined in time: closed, unless its page is still being opened (waiting in the
      // check queue behind checks of up to `checkTimeoutMs` each, review M4-1 P13), and
      // then at the latest after two more check time limits.
      const documentName = `page:${page[1]}`;
      const giveUpAt = Date.now() + handshakeTimeoutMs + 2 * checkTimeoutMs;
      let joining;
      const waitForJoin = (ms) => {
        joining = setTimeout(() => {
          if (extension.joined.has(ws)) return;
          if (extension.loading.has(documentName) && Date.now() < giveUpAt) {
            return waitForJoin(Math.min(500, giveUpAt - Date.now()));
          }
          ws.close(...CLOSE.handshakeTimeout);
        }, ms);
        joining.unref();
      };
      waitForJoin(handshakeTimeoutMs);
      const headers = new Headers();
      for (const name of ["cookie", "origin"]) {
        if (request.headers[name]) headers.set(name, request.headers[name]);
      }
      const context = { socket: ws, pageId: page[1], generation: Number(generation) };
      const client = hocuspocus.handleConnection(
        ws,
        new Request(`http://collab${url.pathname}`, { headers }),
        context,
      );
      lastHeard.set(ws, Date.now());
      ws.on("message", (data) => {
        lastHeard.set(ws, Date.now());
        client.handleMessage(new Uint8Array(data));
      });
      ws.on("pong", () => client.touch?.());
      ws.on("error", () => ws.terminate());
      ws.on("close", (code, reason) => {
        clearTimeout(joining);
        release();
        if (people.has(ws)) held.give(people.get(ws));
        people.delete(ws);
        sockets.delete(ws);
        client.handleClose({ code, reason: reason.toString() });
      });
    });
  });

  const timer = setInterval(() => {
    extension
      .checkAll(hocuspocus)
      .catch((error) => log("live check failed", { error: error.name }));
    const quietSince = Date.now() - idleTimeoutMs;
    for (const ws of sockets) {
      if ((lastHeard.get(ws) ?? Infinity) < quietSince) ws.close(...CLOSE.idle);
      else ws.ping();
    }
  }, checkIntervalMs);
  timer.unref();

  return {
    httpServer,
    hocuspocus,
    extension,
    connections: () => sockets.size,
    listen(port, host) {
      return new Promise((resolve) =>
        httpServer.listen(port, host, () => resolve(httpServer.address())),
      );
    },
    /** Stop accepting, save what is unsaved, close every connection. */
    close() {
      closing ??= (async () => {
        clearInterval(timer);
        httpServer.close();
        hocuspocus.flushPendingStores();
        for (const ws of sockets) ws.close(1012, "restart");
        const deadline = Date.now() + 10_000;
        while (hocuspocus.getDocumentsCount() > 0 && Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
        for (const ws of sockets) ws.terminate();
        await checks.close();
      })();
      return closing;
    },
  };
}

function positive(value, fallback) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

async function main(env) {
  if (!env.HERD_INTERNAL_TOKEN) {
    console.error("HERD_INTERNAL_TOKEN is not set: live editing needs it");
    process.exit(2);
  }
  const server = createCollabServer({
    apiUrl: env.HERD_COLLAB_API_URL || `http://127.0.0.1:${env.HERD_INTERNAL_PORT || 9090}`,
    token: env.HERD_INTERNAL_TOKEN,
    publicUrl: env.HERD_PUBLIC_URL || null,
    cookieName: env.HERD_SESSION_COOKIE_NAME || "herd_session",
    maxPerSession: positive(env.HERD_COLLAB_MAX_PER_SESSION, 10),
    maxPerPage: positive(env.HERD_COLLAB_MAX_PER_PAGE, 3),
    maxPerPerson: positive(env.HERD_COLLAB_MAX_PER_PERSON, 20),
    checkWorkers: positive(env.HERD_COLLAB_CHECK_WORKERS, 1),
    checkTimeoutMs: positive(env.HERD_COLLAB_CHECK_TIMEOUT_SECONDS, 10) * 1000,
    memoryBudgetBytes: positive(env.HERD_COLLAB_MEMORY_BUDGET_MB, DEFAULT_BUDGET_MB) * 1024 * 1024,
    idleTimeoutMs: positive(env.HERD_COLLAB_IDLE_MINUTES, 15) * 60_000,
  });
  const host =
    env.HERD_COLLAB_HOST || ((env.HERD_ROLE || "all") === "all" ? "127.0.0.1" : "0.0.0.0");
  const address = await server.listen(Number(env.HERD_COLLAB_PORT || 1234), host);
  console.log(JSON.stringify({ message: "collab listening", port: address.port, host }));
  for (const signal of ["SIGTERM", "SIGINT"]) {
    process.on(signal, () => server.close().then(() => process.exit(0)));
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main(process.env);
}
