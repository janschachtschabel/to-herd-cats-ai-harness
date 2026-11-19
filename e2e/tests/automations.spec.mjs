// Automations in real browsers (plan M7 task 10), with the OpenAI stub as the only
// provider and the app's settable clock (`clockTo()`, only in this harness) instead of
// waiting for terms: (a) a recurring automation made in the form from a preset, with
// its preview, comes due and runs exactly once, its answer in the DM; "run now" while
// it runs is skipped as busy; (b) a channel automation opens a thread per term, live
// for another member; (c) a heartbeat answering HEARTBEAT_OK leaves no trace but the
// log, one with something to say delivers it; (d) a person without AI sees no
// automation at all. Budgets and owners: automations-limits; event rules and the page
// review: automations-rules.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, signIn, teamSpace } from "./helpers.mjs";
import { channel, closePages, message, openLive, person } from "./messaging-helpers.mjs";
import { aiBasics, scriptStub } from "./ai-helpers.mjs";
import { levelAgent, member, messages } from "./agents-helpers.mjs";
import {
  daily,
  doneRun,
  dueNow,
  firings,
  heartbeat,
  loggedTerms,
  makeAutomation,
  removeAutomations,
  resetClock,
  unread,
} from "./automations-helpers.mjs";

test.describe.configure({ mode: "serial" });

const HUGO = { email: "hugo@e2e.example", password: "e2e-password-654", name: "Hugo" };
let anna;
let ben;
let me; // Anna as the API knows her
let mira; // level 1: answers, reads
let space;
let takt; // a channel of the space
const made = []; // automations to remove after each scenario

const agentSays = (scope, text) => message(scope, "Mira", text);
// System entries in the conversation itself (an open thread repeats its root).
const system = (page, text) =>
  page
    .getByRole("region", { name: "Gespräch" })
    .locator("[data-kind=system]")
    .filter({ hasText: text });
const started = () => `Aufgabe von ${me.name} gestartet.`;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  me = await signIn(anna, OWNER);
  const { connection } = await aiBasics(anna);
  mira = await levelAgent(anna, "Mira", connection, 1);
  space = await teamSpace(anna, "Taktgeber");
  await member(anna, space.id, { type: "agent", id: mira.id }, "editor");
  takt = await channel(anna, space.id, "takt");
  ben = await browser.newContext();
  await signIn(ben, MEMBER);
});

test.beforeEach(async () => scriptStub(anna.request));

test.afterEach(async () => {
  await closePages(anna, ben);
  await removeAutomations(anna, made.splice(0));
});

test.afterAll(async () => {
  if (anna) await resetClock(anna.request);
  await anna?.close();
  await ben?.close();
});

test("a recurring automation from a preset comes due and runs once; run now meanwhile is busy", async () => {
  const page = await openLive(anna, "/automations");
  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("radio", { name: /^Wiederkehrend/ }).check();
  await dialog.getByRole("combobox", { name: "Agent" }).fill("Mira");
  await page.getByRole("option", { name: /Mira/ }).click();
  await dialog.getByRole("radio", { name: "Meine Direktnachricht mit dem Agenten" }).check();
  await dialog.getByRole("textbox", { name: "Auftrag" }).fill("Fasse die offenen Punkte zusammen.");
  await dialog.getByRole("combobox", { name: "Zeitplan" }).selectOption("daily");
  await dialog.getByLabel("Uhrzeit").fill("07:30");
  const preview = dialog.getByRole("list", { name: "Die nächsten Termine" });
  await expect(preview.getByRole("listitem")).toHaveCount(5);
  await expect(preview.getByRole("listitem").first()).toContainText("07:30");
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(page).toHaveURL(/\/automations\/[0-9a-f-]{36}$/);
  const id = page.url().split("/").at(-1);
  made.push(id);
  const log = page.getByRole("list", { name: "Protokoll der Termine" });

  // The run's answer comes slowly: the run is still at work when "run now" is pressed.
  await scriptStub(anna.request, {
    replies: [{ content: "Drei Punkte sind offen.", delay: 12 }],
  });
  const before = await dueNow(anna, id);
  await expect(log.getByTestId("firing-row")).toHaveCount(1, { timeout: 30_000 });
  await expect(log.getByTestId("firing-row").first()).toHaveAttribute("data-outcome", "started");
  await page
    .getByRole("group", { name: "Aktionen" })
    .getByRole("button", { name: "Jetzt ausführen" })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Termin ausgelöst: Übersprungen: Der vorige Lauf arbeitete noch" }),
  ).toBeVisible();
  await expect(log.locator("[data-outcome=skipped_busy]")).toHaveCount(1);

  const [term, busy] = await loggedTerms(anna, id, 2);
  expect(term).toMatchObject({ outcome: "started", due_at: before.next_due_at });
  expect(busy).toMatchObject({ outcome: "skipped_busy", run_id: null });
  await doneRun(anna, term.run_id);
  const dm = await openLive(anna, `/c/${before.place.conversation_id}`);
  await expect(agentSays(dm, "Drei Punkte sind offen.")).toHaveCount(1);
  // Exactly once: the next term moved on in the same transaction as the run.
  const after = await call(anna, "GET", `/api/automations/${id}`);
  expect(new Date(after.next_due_at).getTime()).toBeGreaterThan(
    new Date(before.next_due_at).getTime(),
  );
  expect((await firings(anna, id)).filter((f) => f.outcome === "started")).toHaveLength(1);
  const answers = (await messages(anna, before.place.conversation_id)).filter(
    (m) => m.body_md === "Drei Punkte sind offen.",
  );
  expect(answers).toHaveLength(1);
});

test("a channel automation opens a thread per term, live for another member", async () => {
  const automation = await makeAutomation(anna, {
    agent_id: mira.id,
    place: { type: "channel", conversation_id: takt.id },
    instruction: "Berichte den Stand im Kanal.",
    schedule: daily(8),
  });
  made.push(automation.id);
  const page = await openLive(ben, `/c/${takt.id}`);
  for (const [n, text] of [
    [1, "Erster Bericht."],
    [2, "Zweiter Bericht."],
  ]) {
    await scriptStub(anna.request, { replies: [{ content: text }] });
    if (n === 1) await dueNow(anna, automation.id);
    else await call(anna, "POST", `/api/automations/${automation.id}/run`);
    await expect(system(page, started())).toHaveCount(n, { timeout: 30_000 });
    const open = page.getByRole("button", { name: `Thread „${started()}“ öffnen, 1 Antwort` });
    await expect(open).toHaveCount(n, { timeout: 30_000 });
    await open.nth(n - 1).click();
    const thread = page.getByRole("complementary", { name: "Thread" });
    await expect(agentSays(thread, text)).toBeVisible();
  }
  // Not a word of the instruction in the channel.
  await expect(page.getByText("Berichte den Stand im Kanal.")).toHaveCount(0);
  const top = (await messages(anna, takt.id)).filter((m) => m.kind === "system");
  expect(top).toHaveLength(2);
});

test("a heartbeat answering HEARTBEAT_OK stays silent; one with something to say delivers it", async () => {
  const puls = await channel(anna, space.id, "puls");
  const automation = await makeAutomation(anna, {
    agent_id: mira.id,
    place: { type: "channel", conversation_id: puls.id },
    instruction: "- Läuft die nächtliche Sicherung?",
    schedule: heartbeat(),
  });
  made.push(automation.id);
  const page = await openLive(ben, `/c/${puls.id}`);
  const counts = [await unread(anna), await unread(ben)];

  await scriptStub(anna.request, { replies: [{ content: "HEARTBEAT_OK" }] });
  await dueNow(anna, automation.id);
  const [term] = await loggedTerms(anna, automation.id, 1);
  expect(term).toMatchObject({ outcome: "started" });
  await doneRun(anna, term.run_id);
  // The term notes `heartbeat_ok` in the transaction that ends its run
  // (`automations/runs.py`), so it is read again once the run is done.
  const [ok] = await firings(anna, automation.id);
  expect(ok).toMatchObject({ outcome: "started", heartbeat_ok: true });
  // Nothing at the place, nothing in anyone's activity; only the log says so.
  expect(await messages(anna, puls.id)).toEqual([]);
  expect([await unread(anna), await unread(ben)]).toEqual(counts);
  await expect(page.locator("[data-kind=system]")).toHaveCount(0);
  await expect(page.getByRole("article")).toHaveCount(0);
  const detail = await openLive(anna, `/automations/${automation.id}`);
  const log = detail.getByRole("list", { name: "Protokoll der Termine" });
  await expect(log.getByTestId("firing-row")).toHaveText([
    /Nichts zu melden \(HEARTBEAT_OK, still\)/,
  ]);

  await scriptStub(anna.request, { replies: [{ content: "Die Sicherung ist fehlgeschlagen." }] });
  await dueNow(anna, automation.id);
  await expect(system(page, started())).toHaveCount(1, { timeout: 30_000 });
  await page.getByRole("button", { name: `Thread „${started()}“ öffnen, 1 Antwort` }).click();
  const thread = page.getByRole("complementary", { name: "Thread" });
  await expect(agentSays(thread, "Die Sicherung ist fehlgeschlagen.")).toBeVisible();
  await expect(log.getByTestId("firing-row")).toHaveCount(2);
  const terms = await firings(anna, automation.id);
  expect(terms.map((f) => f.heartbeat_ok)).toEqual([true, false]);
});

test("a person without AI sees no automation at all", async ({ browser }) => {
  const hugo = await person(anna, HUGO);
  await call(anna, "PUT", `/api/ai/assignments/users/${hugo.id}`, { no_ai: true, version: null });
  await member(anna, space.id, { type: "user", id: hugo.id }, "viewer");
  const automation = await makeAutomation(anna, {
    agent_id: mira.id,
    place: { type: "channel", conversation_id: takt.id },
    instruction: "Berichte den Stand im Kanal.",
    schedule: daily(8),
  });
  made.push(automation.id);
  const context = await browser.newContext();
  try {
    await signIn(context, HUGO);
    const page = await context.newPage();
    await page.goto(`/c/${takt.id}`);
    await expect(system(page, started()).first()).toBeVisible(); // the terms of before
    await expect(page.getByRole("link", { name: "Aufgabe ansehen" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Meine Aufgaben" })).toHaveCount(0);
    await page.goto(`/spaces/${space.id}`);
    const tabs = page.getByRole("navigation", { name: "Ansichten des Bereichs" });
    await expect(tabs.getByRole("link", { name: "Board" })).toBeVisible();
    await expect(tabs.getByRole("link", { name: "Aufgaben" })).toHaveCount(0);
    for (const path of ["/automations", `/automations/${automation.id}`]) {
      await page.goto(path);
      await expect(
        page.getByText(/Seite nicht gefunden|Diese Aufgabe gibt es nicht/),
      ).toBeVisible();
    }
    for (const path of [
      "/api/automations",
      `/api/automations/${automation.id}`,
      `/api/automations/${automation.id}/firings`,
      `/api/spaces/${space.id}/automations`,
    ]) {
      expect((await context.request.get(path)).status(), path).toBe(404);
    }
  } finally {
    await context.close();
  }
});
