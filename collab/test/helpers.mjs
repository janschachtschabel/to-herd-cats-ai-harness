// Test helpers: a fake internal API, Hocuspocus clients carrying a grant (as the API's
// relay sends it: `Authorization: Bearer herd_cg_...`).
import { createServer } from "node:http";
import { HocuspocusProvider } from "@hocuspocus/provider";
import WebSocket from "ws";
import * as Y from "yjs";

export const PAGE = "01a1d2d9-2de5-75db-9dc6-a6fa1307273d";
export const ORIGIN = "http://wiki.example";

/** The internal API as the collab process sees it; answers can be changed per test. */
export async function fakeApi({ markdown = "# Start", generation = 0 } = {}) {
  const state = {
    generation,
    markdown,
    epoch: 1, // the asking instance's binding to the page (plan M9 decision 17)
    announcements: [], // each instance heartbeat: { id, url, draining }
    releases: [], // the ids of instances that let go of their pages
    sequence: [], // "announce" | "announce:draining" | "save" | "release", in order
    // grant -> [opaque login session, person, name]. The relay issues a grant per
    // connection; here connections of one person and login share theirs.
    users: {
      herd_cg_a: ["session-a", "user-a", "Anna"],
      herd_cg_b: ["session-b", "user-b", "Ben"],
      herd_cg_a2: ["session-a2", "user-a", "Anna"], // Anna's second login
    },
    pages: {}, // page id -> Markdown, for pages other than `markdown`
    saves: [],
    checks: [],
    unrepresentable: 0,
    loadMutations: 0,
    authDelayMs: 0, // how long the API takes to answer an authentication
    authCalls: 0,
    saveAnswer: () => [200, { generation: state.generation, version: 2 }],
    checkAnswer: () => [
      200,
      {
        generation_ok: true,
        generation: state.generation,
        revoked_grants: [],
        ended_grants: [],
      },
    ],
    tokens: [],
    loadGrants: [], // the X-Herd-Grant of each load
  };
  const server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    const json = body ? JSON.parse(body) : null;
    state.tokens.push(request.headers["x-herd-internal-token"]);
    const url = new URL(request.url, "http://api");
    const reply = ([status, payload]) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(payload));
    };
    if (url.pathname === "/internal/collab/instances" && request.method === "POST") {
      state.announcements.push(json);
      state.sequence.push(json.draining ? "announce:draining" : "announce");
      response.writeHead(204);
      return response.end();
    }
    if (url.pathname.startsWith("/internal/collab/instances/") && request.method === "DELETE") {
      state.releases.push(url.pathname.split("/").pop());
      state.sequence.push("release");
      response.writeHead(204);
      return response.end();
    }
    if (url.pathname === "/internal/collab/auth") {
      state.authCalls++;
      if (state.authDelayMs) await new Promise((resolve) => setTimeout(resolve, state.authDelayMs));
      state.auths = [...(state.auths ?? []), json];
      const user = state.users[json.grant];
      if (!user) return reply([401, { error: { code: "collab.grant_invalid" } }]);
      return reply([
        200,
        {
          user: { id: user[1], name: user[2] },
          session_ref: user[0],
          generation: state.generation,
          can_edit: true,
          epoch: state.epoch,
        },
      ]);
    }
    if (url.pathname.endsWith("/load-mutation")) {
      state.loadMutations++;
      response.writeHead(204);
      return response.end();
    }
    if (url.pathname.endsWith("/unrepresentable")) {
      state.unrepresentable++;
      response.writeHead(204);
      return response.end();
    }
    if (request.method === "GET") {
      state.loadGrants.push(request.headers["x-herd-grant"]);
      state.loadInstances = [...(state.loadInstances ?? []), url.searchParams.get("instance_id")];
      const pageId = url.pathname.split("/")[4];
      return reply([
        200,
        {
          generation: state.generation,
          ydoc_b64: state.ydoc ?? null,
          content_md: state.pages[pageId] ?? state.markdown,
          title: "T",
          epoch: state.epoch,
        },
      ]);
    }
    if (request.method === "PUT") {
      state.saves.push(json);
      state.sequence.push("save");
      return reply(state.saveAnswer(json));
    }
    state.checks.push(json);
    return reply(state.checkAnswer(json));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  state.url = `http://127.0.0.1:${server.address().port}`;
  state.close = () => new Promise((resolve) => server.close(resolve));
  return state;
}

function socketWith(headers) {
  return class extends WebSocket {
    constructor(url, protocols) {
      super(url, protocols, { headers });
      // A browser closes a connecting socket quietly; `ws` emits an error the provider
      // no longer listens to once destroyed, which Node raises as uncaught.
      this.on("error", () => {});
    }
  };
}

/** A browser-like client: provider, document, and every close event it saw. `grant` is
 * sent the way the API's relay sends it; `cookie` only as a browser would (the
 * integration test goes through the relay). */
export function client(url, { grant, cookie, origin = ORIGIN, name = `page:${PAGE}` } = {}) {
  const headers = { origin };
  if (grant) headers.authorization = `Bearer ${grant}`;
  if (cookie) headers.cookie = cookie;
  const doc = new Y.Doc();
  const closes = [];
  const provider = new HocuspocusProvider({
    url,
    name,
    document: doc,
    token: "ignored",
    WebSocketPolyfill: socketWith(headers),
    onClose: ({ event }) => closes.push(event.code),
  });
  return { doc, provider, closes, destroy: () => provider.destroy() };
}

export function synced(c) {
  return new Promise((resolve) => {
    if (c.provider.synced) return resolve();
    c.provider.on("synced", () => resolve());
  });
}

export async function until(predicate, timeoutMs = 4000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(`timed out waiting for ${predicate}`);
}

/** Type text at the end of the first paragraph, as an editor would. */
export function type(doc, text) {
  const fragment = doc.getXmlFragment("default");
  let paragraph = fragment.toArray().find((node) => node.nodeName === "paragraph");
  if (!paragraph) {
    paragraph = new Y.XmlElement("paragraph");
    fragment.push([paragraph]);
  }
  let node = paragraph.get(0);
  if (!(node instanceof Y.XmlText)) {
    node = new Y.XmlText();
    paragraph.insert(0, [node]);
  }
  node.insert(node.length, text);
}

/** A collab server against a fake API, with `open()` for clients; `stop()` ends all. */
export async function liveFixture({ markdown, createCollabServer, ...options } = {}) {
  const api = await fakeApi(markdown === undefined ? {} : { markdown });
  const server = createCollabServer({
    apiUrl: api.url,
    token: "i".repeat(40),
    publicUrl: ORIGIN,
    checkIntervalMs: 100,
    debounceMs: 50,
    maxDebounceMs: 200,
    retryMs: 50,
    log: () => {},
    ...options,
  });
  const address = await server.listen(0, "127.0.0.1");
  const base = `ws://127.0.0.1:${address.port}`;
  const clients = [];
  return {
    api,
    server,
    base,
    metricsUrl: `http://127.0.0.1:${address.port}/metrics`,
    open(clientOptions, { generation = 0, page = PAGE } = {}) {
      const c = client(`${base}/collab/${page}?generation=${generation}`, clientOptions);
      clients.push(c);
      return c;
    },
    async stop() {
      for (const c of clients.splice(0)) c.destroy();
      await server.close();
      await api.close();
    },
  };
}
