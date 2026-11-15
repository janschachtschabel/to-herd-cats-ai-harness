// Automations meet their limits in real browsers (plan M7 task 10), with the OpenAI
// stub and the app's settable clock (only in this harness): (a) an agent's daily
// budget stops a run with a notice that names the limit, and the next term is skipped;
// (b) its owner deactivated, an automation pauses at its term, the agent's responsible
// person is told in the activity view and takes it over.
import { expect, test } from "@playwright/test";
import { OWNER, call, signIn, teamSpace } from "./helpers.mjs";
import { channel, closePages, openLive, person } from "./messaging-helpers.mjs";
import { aiBasics, scriptStub } from "./ai-helpers.mjs";
import { levelAgent, member } from "./agents-helpers.mjs";
import {
  daily,
  doneRun,
  dueNow,
  firings,
  loggedTerms,
  makeAutomation,
  removeAutomations,
  resetClock,
} from "./automations-helpers.mjs";

test.describe.configure({ mode: "serial" });

const CARLA = { email: "carla@e2e.example", password: "e2e-password-321", name: "Carla" };
let anna;
let me; // Anna as the API knows her
let connection;
let mira; // level 1
let space;
let takt; // a channel of the space
const made = []; // automations to remove after each scenario

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  me = await signIn(anna, OWNER);
  ({ connection } = await aiBasics(anna));
  mira = await levelAgent(anna, "Mira", connection, 1);
  space = await teamSpace(anna, "Grenzwerte");
  await member(anna, space.id, { type: "agent", id: mira.id }, "editor");
  takt = await channel(anna, space.id, "grenzen");
});

test.beforeEach(async () => scriptStub(anna.request));

test.afterEach(async () => {
  await closePages(anna);
  await removeAutomations(anna, made.splice(0));
});

test.afterAll(async () => {
  if (anna) await resetClock(anna.request);
  await anna?.close();
});

test("a budget stops a run with a notice and skips the next term", async () => {
  const bruno = await levelAgent(anna, "Bruno", connection, 1);
  const budget = await call(anna, "PUT", `/api/ai/budgets/agents/${bruno.id}`, {
    tokens_per_day: 1,
    version: null,
  });
  try {
    const automation = await makeAutomation(anna, {
      agent_id: bruno.id,
      place: { type: "dm" },
      instruction: "Sieh nach, welche Bereiche es gibt.",
      // One term in a minute and a half: the budget's day is the UTC day of the clock that
      // fires the term, so this scenario comes first, before the clock moves by days.
      schedule: { kind: "once", at: new Date(Date.now() + 90_000).toISOString() },
    });
    made.push(automation.id);
    // The first model call is allowed (nothing used yet) and uses more than the limit;
    // the second, after the tool, is not made.
    await scriptStub(anna.request, {
      replies: [{ tool_calls: [{ name: "list_tree", arguments: {} }] }, { content: "Nie gesagt." }],
    });
    const page = await openLive(anna, `/automations/${automation.id}`);
    await page
      .getByRole("group", { name: "Aktionen" })
      .getByRole("button", { name: "Jetzt ausführen" })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Termin ausgelöst: Gestartet" }),
    ).toBeVisible();
    const [term] = await loggedTerms(anna, automation.id, 1);
    const run = await doneRun(anna, term.run_id);
    expect(run.stop_reason).toBe("budget");
    const dm = await openLive(anna, `/c/${automation.place.conversation_id}`);
    await expect(
      dm.getByText(
        "Das Tagesbudget für KI ist erreicht; der Lauf wurde vor dem nächsten Modellaufruf beendet.",
      ),
    ).toBeVisible();
    await expect(dm.getByText("Nie gesagt.")).toHaveCount(0);
    await dm.goto(`/runs/${run.id}`);
    await expect(dm.getByText("Erreicht: das Tageslimit dieses Agenten.")).toBeVisible();

    await dueNow(anna, automation.id);
    const [, skipped] = await loggedTerms(anna, automation.id, 2);
    expect(skipped).toMatchObject({ outcome: "skipped_budget", run_id: null });
    await page.reload();
    await expect(page.getByTestId("firing-row").first()).toContainText(
      "Übersprungen: Ein Tagesbudget war erreicht",
    );
  } finally {
    await call(anna, "DELETE", `/api/ai/budgets/${budget.id}?version=${budget.version}`);
  }
});

test("its owner deactivated, an automation pauses; the responsible person is told and takes over", async ({
  browser,
}) => {
  const carla = await person(anna, CARLA);
  await member(anna, space.id, { type: "user", id: carla.id }, "editor");
  const context = await browser.newContext();
  let automation;
  try {
    await signIn(context, CARLA);
    automation = await makeAutomation(context, {
      agent_id: mira.id,
      place: { type: "channel", conversation_id: takt.id },
      instruction: "Erinnere an den Wochenplan.",
      schedule: daily(10),
    });
    made.push(automation.id);
  } finally {
    await context.close();
  }
  await call(anna, "POST", `/api/admin/users/${carla.id}/deactivate`);
  try {
    const page = await openLive(anna, "/activity");
    await dueNow(anna, automation.id);
    const entry = page.getByRole("listitem").filter({
      hasText:
        "Eine Aufgabe mit Mira ist angehalten: Wer sie besitzt, darf sie nicht mehr ausführen.",
    });
    await expect(entry).toBeVisible({ timeout: 30_000 });
    await entry.getByRole("button", { name: "Öffnen" }).click();
    await expect(page).toHaveURL(new RegExp(`/automations/${automation.id}$`));
    await expect(
      page.getByText("Angehalten: Wer sie besitzt, darf sie nicht mehr ausführen").first(),
    ).toBeVisible();
    await page
      .getByRole("group", { name: "Aktionen" })
      .getByRole("button", { name: "Übernehmen" })
      .click();
    const confirm = page.getByRole("dialog", { name: "Aufgabe übernehmen?" });
    await confirm.getByRole("button", { name: "Übernehmen" }).click();
    // Hers now: she may change it (only an owner may), and it runs again.
    const actions = page.getByRole("group", { name: "Aktionen" });
    await expect(actions.getByRole("button", { name: "Bearbeiten" })).toBeVisible();
    await expect(actions.getByRole("button", { name: "Übernehmen" })).toHaveCount(0);
    const taken = await call(anna, "GET", `/api/automations/${automation.id}`);
    expect(taken).toMatchObject({ state: "active", paused_reason: null, owner: { id: me.id } });
    expect(await firings(anna, automation.id)).toEqual([]); // a pause logs no term
  } finally {
    await call(anna, "POST", `/api/admin/users/${carla.id}/reactivate`);
  }
});
