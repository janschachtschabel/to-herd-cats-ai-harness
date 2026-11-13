// Test helpers: a fake internal API, Hocuspocus clients with a session cookie.
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
    users: {
      "token-a": ["session-a", "user-a", "Anna"],
      "token-b": ["session-b", "user-b", "Ben"],
    },
    saves: [],
    checks: [],
    saveAnswer: () => [200, { generation: state.generation, version: 2 }],
    checkAnswer: () => [
      200,
      {
        generation_ok: true,
        generation: state.generation,
        revoked_session_ids: [],
        revoked_user_ids: [],
      },
    ],
    tokens: [],
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
    if (url.pathname === "/internal/collab/auth") {
      const user = state.users[json.session_token];
      if (!user) return reply([401, { error: { code: "collab.session_invalid" } }]);
      return reply([
        200,
        {
          user: { id: user[1], name: user[2] },
          session_id: user[0],
          generation: state.generation,
          can_edit: true,
        },
      ]);
    }
    if (request.method === "GET") {
      return reply([
        200,
        { generation: state.generation, ydoc_b64: null, content_md: state.markdown, title: "T" },
      ]);
    }
    if (request.method === "PUT") {
      state.saves.push(json);
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
    }
  };
}

/** A browser-like client: provider, document, and every close event it saw. */
export function client(url, { cookie, origin = ORIGIN, name = `page:${PAGE}` } = {}) {
  const headers = { origin };
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
