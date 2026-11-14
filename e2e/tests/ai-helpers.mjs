// Setting up AI scenarios: the OpenAI stub (started by global-setup.mjs on the public
// port + 3) and AI connections, the standard assignment and agents through the API.
import { expect } from "@playwright/test";
import { OWNER, call } from "./helpers.mjs";

const port = Number(process.env.HERD_E2E_PORT || 18080);
export const STUB = `http://127.0.0.1:${port + 3}`;
/** What the app calls: the stub's OpenAI routes (a `local` connection may use http). */
export const STUB_API = `${STUB}/v1`;

/** Clears the stub's script and log, then queues `replies` (`{content}` or
 *  `{tool_calls: [{name, arguments}]}`) and other settings (`delay`, `failures`). */
export async function scriptStub(request, script = {}) {
  expect((await request.post(`${STUB}/_stub/reset`)).ok()).toBeTruthy();
  if (Object.keys(script).length === 0) return;
  expect((await request.post(`${STUB}/_stub/script`, { data: script })).ok()).toBeTruthy();
}

/** Everything the stub has received, as one string to search. */
export async function stubLog(request) {
  const r = await request.get(`${STUB}/_stub/log`);
  expect(r.ok()).toBeTruthy();
  return JSON.stringify(await r.json());
}

async function connectionNamed(admin, name) {
  const list = await call(admin, "GET", "/api/ai/connections?limit=100");
  return list.items.find((c) => c.name === name) ?? null;
}

/** A connection to the stub (found again by name on later calls). */
export async function stubConnection(admin, name, dataLocation = "local") {
  return (
    (await connectionNamed(admin, name)) ??
    (await call(admin, "POST", "/api/ai/connections", {
      name,
      kind: "local",
      base_url: STUB_API,
      models: ["gpt-6-luna"],
      data_location: dataLocation,
    }))
  );
}

/** Everyone has AI through the standard assignment to `connection` (unless set). */
export async function standardAssignment(admin, connection) {
  const overview = await call(admin, "GET", "/api/ai/assignments");
  if (overview.default) return overview.default;
  await call(admin, "PUT", "/api/ai/assignments/default", {
    target: { connection_id: connection.id, model: connection.models[0] },
    version: overview.version,
  });
  return (await call(admin, "GET", "/api/ai/assignments")).default;
}

/** An active agent on `connection` (found again by name; made active again). */
export async function agent(admin, name, connection) {
  const owner = (await call(admin, "GET", "/api/auth/me")).user;
  const list = await call(admin, "GET", "/api/agents?limit=100");
  const found = list.items.find((a) => a.name === name);
  if (found) {
    if (found.status === "active") return found;
    return call(admin, "PATCH", `/api/agents/${found.id}`, {
      status: "active",
      version: found.version,
    });
  }
  return call(admin, "POST", "/api/agents", {
    name,
    intro: `${name} beantwortet Fragen.`,
    instructions: "Antworte kurz und auf Deutsch.",
    connection_id: connection.id,
    model: connection.models[0],
    responsible_user_id: owner.id,
    status: "active",
  });
}

/** The basic setup the scenarios share: a stub connection, AI for everyone, Hilda. */
export async function aiBasics(admin) {
  const connection = await stubConnection(admin, "Stub");
  await standardAssignment(admin, connection);
  return { connection, hilda: await agent(admin, "Hilda", connection) };
}

export { OWNER };
