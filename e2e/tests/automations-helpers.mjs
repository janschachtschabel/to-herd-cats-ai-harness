// Setting up automations (plan M7 task 10): the app's settable clock, automations and
// their log through the API, and waiting for their runs.
import { execFileSync } from "node:child_process";
import { expect } from "@playwright/test";
import { call } from "./helpers.mjs";

const port = Number(process.env.HERD_E2E_PORT || 18080);
const CONTROL = `http://127.0.0.1:${port + 4}`;

async function offset(request) {
  const r = await request.get(`${CONTROL}/clock`);
  expect(r.ok()).toBeTruthy();
  return (await r.json()).offset_seconds;
}

async function setOffset(request, seconds) {
  const r = await request.post(`${CONTROL}/clock`, { data: { offset_seconds: seconds } });
  expect(r.ok()).toBeTruthy();
}

/**
 * Moves the app's clock (the one that schedules: due loop, event rules, page review;
 * `global-setup.mjs`) forward to `at` (a Date or an ISO string); never back. The due
 * loop looks every 5 s, so a term due by then fires within seconds.
 */
export async function clockTo(request, at) {
  const wanted = (new Date(at).getTime() - Date.now()) / 1000;
  const current = await offset(request);
  if (wanted > current) await setOffset(request, wanted);
}

/** Moves the app's clock forward by `seconds` from where it stands. */
export async function advanceClock(request, seconds) {
  await setOffset(request, (await offset(request)) + seconds);
}

/** Puts the app's clock back to the system time (after a file's scenarios). */
export const resetClock = (request) => setOffset(request, 0);

/** Moves the app's clock just past the automation's next term. */
export async function dueNow(context, id) {
  const automation = await call(context, "GET", `/api/automations/${id}`);
  expect(automation.next_due_at).toBeTruthy();
  await clockTo(context.request, new Date(new Date(automation.next_due_at).getTime() + 1000));
  return automation;
}

export const makeAutomation = (context, body) => call(context, "POST", "/api/automations", body);

/** An automation's log, oldest term first. */
export async function firings(context, id) {
  const page = await call(context, "GET", `/api/automations/${id}/firings?limit=100`);
  return page.items.reverse();
}

/** Waits until the log holds `count` terms (`atLeast`: or more); returns them, oldest
 *  first. */
export async function loggedTerms(context, id, count, { atLeast = false } = {}) {
  let found = [];
  const poll = expect.poll(async () => (found = await firings(context, id)).length, {
    timeout: 45_000,
  });
  await (atLeast ? poll.toBeGreaterThanOrEqual(count) : poll.toBe(count));
  return found;
}

/** Waits until the run is done; returns it. */
export async function doneRun(context, runId) {
  let run = null;
  await expect
    .poll(async () => (run = await call(context, "GET", `/api/runs/${runId}`)).state, {
      timeout: 60_000,
    })
    .toBe("done");
  return run;
}

/** Deletes automations that are still there (each scenario cleans up after itself, so
 *  that a later move of the clock fires nothing of it). */
export async function removeAutomations(context, ids) {
  for (const id of ids) {
    const r = await context.request.get(`/api/automations/${id}`);
    if (!r.ok()) continue;
    const { version } = await r.json();
    await call(context, "DELETE", `/api/automations/${id}?version=${version}`);
  }
}

/** Every-day schedules for the API. */
export const daily = (hour = 9) => ({
  kind: "recurring",
  cron: `0 ${hour} * * *`,
  time_zone: "Europe/Berlin",
});
export const heartbeat = () => ({
  kind: "heartbeat",
  interval_minutes: 15,
  active_days: [1, 2, 3, 4, 5, 6, 7],
  active_from: "00:00",
  active_until: "00:00", // equal: the whole day
  time_zone: "UTC",
});
export const onEvent = (event_type, extra = {}) => ({
  kind: "event",
  event_type,
  quiet_seconds: 60,
  ...extra,
});

/** The person's unread activity count (`/api/activity/count`). */
export async function unread(context) {
  return call(context, "GET", "/api/activity/count");
}

/** One value from the scratch database (psql), for what no route tells: how many
 *  events wait for an event rule's quiet time to end. */
export function sql(query) {
  const url = process.env.HERD_E2E_DATABASE_URL.replace("+asyncpg", "");
  return execFileSync("psql", [url, "-tAc", query], { encoding: "utf8" }).trim();
}

/** Waits until `count` events wait for the rule's quiet time to end. */
export async function waitingEvents(id, count) {
  const query = `SELECT count(*) FROM automation_event WHERE automation_id = '${id}' AND firing_id IS NULL`;
  await expect.poll(() => Number(sql(query)), { timeout: 30_000 }).toBe(count);
}
