// Setting up agents at work (plan M6 task 13): agents of a level, tool grants, a
// space they work in, what a run left behind, and restarting the app's worker.
import { expect } from "@playwright/test";
import { call } from "./helpers.mjs";

const port = Number(process.env.HERD_E2E_PORT || 18080);
const CONTROL = `http://127.0.0.1:${port + 4}`;

/**
 * Restarts the worker in the middle of whatever it runs. The app runs in role all
 * (its worker in the same process), so this kills the app's whole process group with
 * SIGKILL (a crash: no orderly stop, a run in progress keeps its lease) and starts it
 * again on the same database; it returns once the new process is ready. The control
 * route lives in `global-setup.mjs` (public port + 4). With the e2e lease of 5 s the
 * new worker takes a crashed run up within seconds and goes on from its journal.
 * Open pages lose their live stream meanwhile: reload them afterwards.
 */
export async function restartApp(request) {
  const r = await request.post(`${CONTROL}/restart-app`, { timeout: 120_000 });
  expect(r.ok(), await r.text()).toBeTruthy();
}

/** An active agent of `level` on `connection` (found again by name). */
export async function levelAgent(admin, name, connection, level) {
  const list = await call(admin, "GET", "/api/agents?limit=100");
  const found = list.items.find((a) => a.name === name);
  if (found) return found;
  const owner = (await call(admin, "GET", "/api/auth/me")).user;
  return call(admin, "POST", "/api/agents", {
    name,
    intro: `${name} arbeitet im Team mit.`,
    instructions: "Arbeite sorgfältig und antworte kurz auf Deutsch.",
    connection_id: connection.id,
    model: connection.models[0],
    responsible_user_id: owner.id,
    status: "active",
    level,
  });
}

/** Sets one tool's grant for an agent (`allow` is the level's default). */
export async function grant(admin, agentId, tool, policy) {
  const agent = await call(admin, "GET", `/api/agents/${agentId}`);
  return call(admin, "PUT", `/api/agents/${agentId}/tools`, {
    tools: [{ tool, policy }],
    version: agent.version,
  });
}

/** Makes `principal` (`{type, id}`) a member of the space with `role`. */
export async function member(admin, spaceId, { type, id }, role) {
  await call(admin, "PUT", `/api/spaces/${spaceId}/members`, {
    member_type: type,
    member_id: id,
    role,
  });
}

/** The messages of a conversation (newest page, top level), oldest first. */
export async function messages(context, conversationId) {
  const page = await call(
    context,
    "GET",
    `/api/conversations/${conversationId}/messages?limit=100`,
  );
  return page.items;
}

/** The newest run of an agent that `context` may read. */
export async function latestRun(context, agentId) {
  const runs = await call(context, "GET", `/api/runs?agent_id=${agentId}&limit=1`);
  return runs.items[0] ?? null;
}

/** Waits until the agent's newest run has finished and returns it. */
export async function finishedRun(context, agentId, after = null) {
  let run = null;
  await expect
    .poll(
      async () => {
        run = await latestRun(context, agentId);
        if (!run || (after && run.id === after)) return "none";
        return run.state;
      },
      { timeout: 60_000 },
    )
    .toBe("done");
  return run;
}

/** Every journal entry of a run, oldest first. */
export async function runEvents(context, runId) {
  const page = await call(context, "GET", `/api/runs/${runId}/events?limit=100`);
  return page.items;
}

/** The OpenAI chat requests the stub received (its log holds every route). */
export function chatRequests(log) {
  return log.filter((r) => r.path === "/v1/chat/completions");
}
