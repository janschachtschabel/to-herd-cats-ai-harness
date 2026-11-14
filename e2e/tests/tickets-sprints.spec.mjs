// Sprints and the new boards in real browsers (plan M4b, task 4): a sprint is planned
// and started in the browser and filled from the backlog by keyboard, live at Ben's;
// the daily view groups by person, marks today's changes and filters by a click; my
// board gathers Ben's tickets from two spaces, moves them by keyboard and menu and
// explains a space without the category; closing the sprint sends the unfinished
// ticket back to the backlog, keeps the tally and writes nothing into any channel.
// The app runs in role all, so its worker writes the timelines.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, signIn, teamSpace } from "./helpers.mjs";
import { closePages, openLive } from "./messaging-helpers.mjs";
import {
  card,
  change,
  conversationsSnapshot,
  myColumn,
  personRow,
  sprintItem,
  status,
  ticket,
  timelineEntry,
} from "./tickets-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let benUser;
let team; // Ben is an editor here
let second; // a second team of Ben's, without a review status
let login;
let exporting;
let elsewhere;

const today = new Date().toISOString().slice(0, 10);
const inTwoWeeks = new Date(Date.now() + 13 * 86_400_000).toISOString().slice(0, 10);

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER);
  team = await teamSpace(anna, "Sprint-Team");
  second = await teamSpace(anna, "Zweites Team");
  benUser = await signIn(ben, MEMBER);
  login = await ticket(anna, team.id, "Login reparieren", { priority: "high" });
  exporting = await ticket(anna, team.id, "Export prüfen");
  elsewhere = await ticket(anna, second.id, "Bericht schreiben");
  await change(anna, elsewhere.number, { assignee: { type: "user", id: benUser.id } });
  const review = await status(anna, second.id, "Zur Prüfung");
  await call(anna, "DELETE", `/api/ticket-statuses/${review.id}?version=${review.version}`);
});

test.afterEach(async () => closePages(anna, ben));

test.afterAll(async () => {
  await anna?.close();
  await ben?.close();
});

test("a sprint is planned and started, filled from the backlog by keyboard, live at Ben's", async () => {
  const sprints = `/spaces/${team.id}/sprints`;
  const b = await openLive(ben, sprints);
  await expect(b.getByText("Noch keine Sprints in diesem Bereich.")).toBeVisible();
  // Ben is an editor: he plans tickets into sprints, but makes none.
  await expect(b.getByRole("button", { name: "Neuer Sprint" })).toHaveCount(0);

  const a = await openLive(anna, sprints);
  await a.getByRole("button", { name: "Neuer Sprint" }).click();
  const dialog = a.getByRole("dialog", { name: "Neuer Sprint" });
  await dialog.getByLabel("Name").fill("Sprint 1");
  await dialog.getByLabel("Ziel").fill("Anmeldung stabil");
  await dialog.getByLabel("Beginn").fill(today);
  await dialog.getByLabel("Ende").fill(inTwoWeeks);
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(sprintItem(a, "Sprint 1")).toContainText("Geplant");
  await expect(sprintItem(b, "Sprint 1")).toContainText("Geplant"); // live (sprint.changed)

  await a.getByRole("button", { name: "Sprint 1 starten" }).click();
  await expect(sprintItem(a, "Sprint 1")).toContainText("Aktiv");
  await expect(sprintItem(b, "Sprint 1")).toContainText("Aktiv");

  // The backlog: pick both tickets by keyboard, into the running sprint.
  await a
    .getByRole("navigation", { name: "Ansichten des Bereichs" })
    .getByRole("link", { name: "Vorrat" })
    .click();
  const first = a.getByRole("checkbox", { name: `${login.key} auswählen` });
  await first.focus();
  await a.keyboard.press("Space");
  await a.keyboard.press("Tab"); // the ticket's link
  await a.keyboard.press("Tab");
  await expect(a.getByRole("checkbox", { name: `${exporting.key} auswählen` })).toBeFocused();
  await a.keyboard.press("Space");
  await expect(a.getByRole("combobox", { name: "Ziel-Sprint" })).toHaveValue(/.+/);
  await expect(
    a.getByRole("combobox", { name: "Ziel-Sprint" }).locator("option:checked"),
  ).toHaveText("Sprint 1 (läuft)");
  await a.getByRole("button", { name: "In Sprint legen (2)" }).click();
  await expect(a.getByText("2 Tickets in Sprint 1 gelegt.")).toBeVisible();
  await expect(a.getByText("Der Vorrat ist leer.")).toBeVisible();

  await b.getByRole("button", { name: "Tickets von Sprint 1 zeigen" }).click();
  await expect(
    sprintItem(b, "Sprint 1").getByRole("link", { name: new RegExp(login.key) }),
  ).toBeVisible();
  await expect(
    sprintItem(b, "Sprint 1").getByRole("link", { name: new RegExp(exporting.key) }),
  ).toBeVisible();

  // The timeline names the sprint (written by the worker).
  const t = await openLive(ben, `/tickets/${login.number}`);
  await expect(timelineEntry(t, "anna hat das Ticket in Sprint 1 gelegt.")).toBeVisible();
  await expect(
    t
      .getByRole("complementary", { name: "Felder des Tickets" })
      .getByRole("combobox", { name: "Sprint" }),
  ).toHaveValue(/.+/);
});

test("the daily view has a row per person, marks today's changes and filters by a click", async ({
  browser,
}) => {
  const working = await status(anna, team.id, "In Arbeit");
  await change(anna, login.number, {
    assignee: { type: "user", id: benUser.id },
    status_id: working.id,
  });
  const a = await openLive(anna, `/spaces/${team.id}/board`);
  await a.getByRole("checkbox", { name: "Nach Person gruppieren" }).check();
  // The daily view starts on the running sprint.
  await expect(a.getByRole("combobox", { name: "Sprint" }).locator("option:checked")).toHaveText(
    "Sprint 1 (läuft)",
  );
  const benRow = personRow(a, "Ben");
  await expect(benRow.getByText("1 Ticket, 1 seit dem letzten Arbeitstag geändert")).toBeVisible();
  const cell = benRow.getByRole("group", { name: "Ben: In Arbeit" });
  await expect(card(cell, login.key)).toContainText("Geändert");
  await expect(card(personRow(a, "Nicht zugewiesen"), exporting.key)).toBeVisible();

  // Ben takes the other ticket elsewhere: it moves into his row, live.
  await change(ben, exporting.number, { assignee: { type: "user", id: benUser.id } });
  await expect(card(benRow, exporting.key)).toBeVisible();
  await expect(personRow(a, "Nicht zugewiesen")).toHaveCount(0);

  // A new ticket for nobody joins the sprint; a click on Ben filters to him, and the
  // filter is lifted again.
  const third = await ticket(anna, team.id, "Noch offen");
  await change(anna, third.number, { sprint_id: (await activeSprint()).id });
  await expect(card(personRow(a, "Nicht zugewiesen"), third.key)).toBeVisible();
  await a.getByRole("button", { name: "Nur Ben zeigen" }).click();
  await expect(a.getByText("Gefiltert auf Ben.")).toBeVisible();
  await expect(personRow(a, "Nicht zugewiesen")).toHaveCount(0);
  await a.getByRole("button", { name: "Alle Personen zeigen" }).click();
  await expect(personRow(a, "Nicht zugewiesen")).toBeVisible();

  // On a phone the rows scroll sideways inside the board, the page never does.
  const phone = await browser.newContext({ viewport: { width: 375, height: 812 } });
  await signIn(phone, OWNER);
  const p = await openLive(phone, `/spaces/${team.id}/board`);
  await p.getByRole("checkbox", { name: "Nach Person gruppieren" }).check();
  await expect(card(personRow(p, "Ben"), login.key)).toBeVisible();
  await expect
    .poll(() => p.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(375);
  await phone.close();
});

test("my board gathers Ben's tickets from two spaces, moves by keyboard and menu, and explains a missing category", async () => {
  const b = await openLive(ben, "/tickets");
  await b.getByRole("link", { name: "Mein Board" }).click();
  await expect(b.getByRole("heading", { name: "Mein Board", level: 1 })).toBeVisible();
  const mine = card(myColumn(b, "Offen"), elsewhere.key);
  await expect(mine).toContainText("Zweites Team");
  await expect(card(myColumn(b, "In Arbeit"), login.key)).toContainText("Sprint-Team");

  // By keyboard: the grip, Space, Right, Space (one turn of the timers after picking up).
  const told = b.getByRole("status").filter({ hasText: elsewhere.key });
  await mine.getByRole("button", { name: `${elsewhere.key} verschieben` }).focus();
  await b.keyboard.press("Space");
  await expect(told).toHaveText(`${elsewhere.key} über Offen.`);
  await b.evaluate(() => new Promise((resolve) => setTimeout(resolve)));
  await b.keyboard.press("ArrowRight");
  await expect(told).toHaveText(`${elsewhere.key} über In Arbeit.`);
  await b.keyboard.press("Space");
  const moved = card(myColumn(b, "In Arbeit"), elsewhere.key);
  await expect(moved).toBeVisible();
  await expect(moved.getByRole("button", { name: `${elsewhere.key} verschieben` })).toBeFocused();
  await expect(moved).toContainText("In Arbeit"); // the first active status of its space

  // The second team has no review status: the move is refused and explained.
  await moved.getByRole("button", { name: `Spalte von ${elsewhere.key} ändern` }).click();
  await b.getByRole("menuitemradio", { name: "Zur Prüfung" }).click();
  await expect(b.getByRole("alert")).toContainText(
    "Zweites Team hat keinen Status der Kategorie Zur Prüfung",
  );
  await expect(card(myColumn(b, "In Arbeit"), elsewhere.key)).toBeVisible();
  await expect(card(myColumn(b, "Zur Prüfung"), elsewhere.key)).toHaveCount(0);

  // The sprint team has one: through the menu, into review.
  await card(b, login.key)
    .getByRole("button", { name: `Spalte von ${login.key} ändern` })
    .click();
  await b.getByRole("menuitemradio", { name: "Zur Prüfung" }).click();
  await expect(card(myColumn(b, "Zur Prüfung"), login.key)).toContainText("Zur Prüfung");
});

test("closing the sprint sends the unfinished back to the backlog, keeps the tally, writes into no channel", async () => {
  const done = await status(anna, team.id, "Erledigt");
  await change(anna, exporting.number, { status_id: done.id });
  const before = { anna: await conversationsSnapshot(anna), ben: await conversationsSnapshot(ben) };

  const a = await openLive(anna, `/spaces/${team.id}/sprints`);
  await a.getByRole("button", { name: "Sprint 1 abschließen" }).click();
  const dialog = a.getByRole("dialog", { name: "Sprint 1 abschließen" });
  await expect(dialog.getByRole("radio", { name: /In den nächsten Sprint/ })).toBeDisabled();
  await expect(dialog.getByRole("radio", { name: "Zurück in den Vorrat" })).toBeChecked();
  await dialog.getByRole("button", { name: "Abschließen" }).click();
  await expect(sprintItem(a, "Sprint 1")).toContainText("Abgeschlossen");
  await expect(sprintItem(a, "Sprint 1")).toContainText("3 geplant · 1 erledigt · 2 übertragen");

  const b = await openLive(ben, `/spaces/${team.id}/backlog`);
  await expect(b.getByRole("link", { name: new RegExp(login.key) })).toBeVisible();
  await expect(b.getByRole("link", { name: new RegExp(exporting.key) })).toHaveCount(0);

  const t = await openLive(ben, `/tickets/${login.number}`);
  await expect(
    timelineEntry(t, "anna hat das Ticket aus Sprint 1 in den Vorrat gelegt."),
  ).toBeVisible();
  expect(await conversationsSnapshot(anna)).toEqual(before.anna);
  expect(await conversationsSnapshot(ben)).toEqual(before.ben);
});

/** The running sprint of the sprint team. */
async function activeSprint() {
  const page = await call(anna, "GET", `/api/spaces/${team.id}/sprints?state=active`);
  return page.items[0];
}
