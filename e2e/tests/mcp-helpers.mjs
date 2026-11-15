// Setting up MCP scenarios (plan M8 task 12): the organisation's MCP switch, calls to
// `/mcp` as an external client makes them (plain HTTP, a bearer token), and the MCP and
// OAuth stubs that global-setup.mjs runs over https for `localhost` (public port + 5
// and + 6; the app trusts their certificate, the tests' requests accept it).
import { expect, request as playwrightRequest } from "@playwright/test";
import { call } from "./helpers.mjs";

const port = Number(process.env.HERD_E2E_PORT || 18080);
export const MCP_STUB = `https://localhost:${port + 5}`;
/** The stub's MCP endpoint, as a server's address (the catalogue entry names it too). */
export const MCP_STUB_URL = `${MCP_STUB}/mcp`;
export const OAUTH_STUB = `https://localhost:${port + 6}`;

/** The MCP stub's tools after a reset (`tests/support/mcp_stub.py`, `default_tools`):
 *  give them again, changed, to change one tool's fingerprint. */
export const STUB_TOOLS = [
  {
    name: "search_issues",
    description: "Search issues by text.",
    input_schema: { type: "object", properties: { q: { type: "string" } } },
    read_only: true,
  },
  {
    name: "create_issue",
    description: "Create an issue.",
    input_schema: { type: "object", properties: { title: { type: "string" } } },
  },
];

/** A request context for the stubs' control routes (their certificate is the run's). */
async function stubs() {
  return playwrightRequest.newContext({ ignoreHTTPSErrors: true });
}

async function control(base, path, data) {
  const context = await stubs();
  try {
    const r =
      data === undefined
        ? await context.get(`${base}${path}`)
        : await context.post(`${base}${path}`, { data });
    expect(r.ok(), `${path}: ${r.status()}`).toBeTruthy();
    return r.json();
  } finally {
    await context.dispose();
  }
}

/** Resets the MCP stub (its default tools: search_issues read-only, create_issue),
 *  then applies `script` (`tools`, `results`, `delay`, `failures`, ...). */
export async function scriptMcp(script = {}) {
  await control(MCP_STUB, "/_stub/reset", {});
  if (Object.keys(script).length > 0) await control(MCP_STUB, "/_stub/script", script);
}

/** Changes the MCP stub's script without resetting it. */
export const amendMcp = (script) => control(MCP_STUB, "/_stub/script", script);

/** Every request the MCP stub received (method, path, headers, body). */
export const mcpStubLog = () => control(MCP_STUB, "/_stub/log");

/** The `tools/call` requests the MCP stub received: tool name and arguments. */
export async function stubToolCalls() {
  const log = await mcpStubLog();
  return log
    .map((r) => (r.body ? JSON.parse(r.body) : null))
    .filter((body) => body?.method === "tools/call")
    .map(({ params }) => ({ name: params.name, arguments: params.arguments }));
}

/** Resets the OAuth stub to its defaults (client `herd-client`, secret by post). */
export const resetOAuth = () => control(OAUTH_STUB, "/_stub/reset", {});

/** The OAuth stub's settings as a client registered there needs them. */
export const OAUTH_CLIENT = {
  client_id: "herd-client",
  client_secret: { value: "client-SECRET-value-42" },
  token_auth: "client_secret_post",
  authorization_endpoint: `${OAUTH_STUB}/authorize`,
  token_endpoint: `${OAUTH_STUB}/token`,
  revocation_endpoint: `${OAUTH_STUB}/revoke`,
  scopes: "mcp",
};

/** Switches MCP for the organisation (`enabled`), data location `external`. */
export async function mcpSwitch(admin, enabled, data_location = "external") {
  const settings = await call(admin, "GET", "/api/ai/mcp");
  if (settings.enabled === enabled && settings.data_location === data_location) return settings;
  return call(admin, "PUT", "/api/ai/mcp", { enabled, data_location, version: settings.version });
}

let rpcId = 0;

/** One JSON-RPC request to `/mcp` with `secret` as the bearer token, as a client sends
 *  it (no cookie, no Origin). Returns `{status, body}`. */
export async function mcpRequest(request, secret, method, params) {
  rpcId += 1;
  const r = await request.fetch("/mcp", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${secret}`,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": "2025-06-18",
    },
    data: { jsonrpc: "2.0", id: rpcId, method, ...(params ? { params } : {}) },
  });
  const text = await r.text();
  return { status: r.status(), body: text ? JSON.parse(text) : null };
}

/** The names of the tools `/mcp` offers the token, sorted. */
export async function mcpTools(request, secret) {
  const { status, body } = await mcpRequest(request, secret, "tools/list");
  expect(status, JSON.stringify(body)).toBe(200);
  return body.result.tools.map((t) => t.name).sort();
}

/** Calls a tool through `/mcp`; returns `{text, isError}` of its result. */
export async function mcpTool(request, secret, name, args = {}) {
  const { status, body } = await mcpRequest(request, secret, "tools/call", {
    name,
    arguments: args,
  });
  expect(status, JSON.stringify(body)).toBe(200);
  expect(body.error, JSON.stringify(body)).toBeUndefined();
  const text = body.result.content.map((c) => c.text ?? "").join("\n");
  return { text, isError: body.result.isError === true };
}

/** A personal token made through the API (its clear text is only in the answer). */
export async function apiToken(context, name, mode, space_ids = null) {
  const made = await call(context, "POST", "/api/tokens", {
    name,
    mode,
    expires_in_days: 7,
    ...(space_ids ? { space_ids } : {}),
  });
  return made;
}

/** An external agent (found again by name) with `owner` as the responsible person. */
export async function externalAgent(admin, name, level = 2) {
  const list = await call(admin, "GET", "/api/agents?limit=100");
  const found = list.items.find((a) => a.name === name);
  if (found) return found;
  const owner = (await call(admin, "GET", "/api/auth/me")).user;
  return call(admin, "POST", "/api/agents", {
    name,
    kind: "external",
    intro: `${name} arbeitet von außen.`,
    responsible_user_id: owner.id,
    status: "active",
    level,
  });
}

/** An MCP server of the organisation on the stub (found again by name). */
export async function stubServer(admin, name, extra = {}) {
  const list = await call(admin, "GET", "/api/ai/mcp-servers?limit=100");
  const found = list.items.find((s) => s.name === name);
  if (found) return found;
  const made = await call(admin, "POST", "/api/ai/mcp-servers", {
    name,
    url: MCP_STUB_URL,
    data_location: "local",
    connector_scope: "none",
    enabled: true,
    ...extra,
  });
  return made.server ?? made;
}

/** The tools of a server as the API lists them, by name. */
export async function serverTools(admin, serverId) {
  const page = await call(admin, "GET", `/api/ai/mcp-servers/${serverId}/tools?limit=100`);
  return Object.fromEntries(page.items.map((t) => [t.name, t]));
}

/** Approves a server's tool by name (at the version it has now). A tool the server
 * annotates read-only is classified `read` first: the system proposes `write` unless
 * the catalogue agrees (module review M8 1, finding 7). */
export async function approveTool(admin, serverId, name) {
  let tool = (await serverTools(admin, serverId))[name];
  if (tool.read_only_hint && tool.classification !== "read") {
    tool = await call(admin, "PATCH", `/api/ai/mcp-servers/${serverId}/tools/${tool.id}`, {
      classification: "read",
      version: tool.version,
    });
  }
  return call(admin, "POST", `/api/ai/mcp-servers/${serverId}/tools/${tool.id}/approve`, {
    version: tool.version,
  });
}

/** The run-tool name (`ext_…`) of a server's tool, from the agent's grants list. */
export async function externalToolName(admin, agentId, serverName, toolName) {
  const tools = await call(admin, "GET", `/api/agents/${agentId}/tools`);
  const found = tools.tools.find(
    (t) => t.external?.server_name === serverName && t.external?.tool_name === toolName,
  );
  expect(found, `${serverName} · ${toolName}`).toBeTruthy();
  return found.name;
}

/** Sets the agent's tool grants to exactly these (`{tool: policy}`; a PUT replaces all
 *  entries, so tools left out fall back to their defaults: an external one is blocked). */
export async function setGrants(admin, agentId, grants) {
  const agent = await call(admin, "GET", `/api/agents/${agentId}`);
  return call(admin, "PUT", `/api/agents/${agentId}/tools`, {
    tools: Object.entries(grants).map(([tool, policy]) => ({ tool, policy })),
    version: agent.version,
  });
}
