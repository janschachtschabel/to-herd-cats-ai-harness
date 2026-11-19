// Tickets in real browsers (plan M4, task 8), part one: creating and assigning reaches
// the other person's activity; a board move by keyboard or menu shows live for the other
// person; a stale tab's move and a stale title edit each get a 409 that loses nothing.
// The app runs in role all, so its worker writes the timeline and the notifications.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, signIn, teamSpace } from "./helpers.mjs";
import { CLARA, closePages, openLive, person } from "./messaging-helpers.mjs";
import { card, change, column, status, ticket } from "./tickets-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let space;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER);
  space = await teamSpace(anna, "Projekt Apfel"); // makes Ben, an editor here
  await person(anna, CLARA); // in the organisation, not in the space
  await signIn(ben, MEMBER);
});

test.afterEach(async () => closePages(anna, ben));

test.afterAll(async () => {
  await anna?.close();
  await ben?.close();
});

test("a new ticket assigned to Ben reaches his activity and his ticket count", async () => {
  const b = await openLive(ben, "/activity");
  await expect(b.getByRole("heading", { name: "Aktivität" })).toBeVisible();

  const a = await openLive(anna, "/tickets");
  await a.getByRole("button", { name: "Neues Ticket" }).click();
  const dialog = a.getByRole("dialog", { name: "Neues Ticket" });
  const where = dialog.getByLabel("Bereich"); // only with more than one space to choose
  if (await where.count()) await where.selectOption({ label: "Projekt Apfel" });
  await dialog.getByLabel("Titel").fill("Anmeldung prüfen");
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(a.getByRole("heading", { name: "Anmeldung prüfen", level: 1 })).toBeVisible();
  const number = Number(new URL(a.url()).pathname.split("/").at(-1));
  const key = `HC-${number}`;

  // The picker offers the space's people only: Clara is not among them.
  await a.getByRole("button", { name: "Jemandem zuweisen" }).click();
  const picker = a.getByRole("combobox", { name: "Zugewiesen an" });
  await picker.fill("Clara");
  await expect(a.getByText("Niemand gefunden.")).toBeVisible();
  await picker.fill("Ben");
  await a.getByRole("option", { name: "Ben" }).click();
  await expect(a.getByRole("button", { name: "Zuweisung lösen" })).toBeVisible();

  // Live at Ben's: the activity entry and the count in the sidebar.
  const entry = b.getByRole("listitem").filter({ hasText: `hat dir ${key} zugewiesen` });
  await expect(entry).toContainText(`anna hat dir ${key} zugewiesen`);
  await expect(b.getByRole("link", { name: /^Tickets.*offenes? Tickets? für dich/ })).toBeVisible();
  await entry.getByRole("button", { name: "Öffnen" }).click();
  await expect(b).toHaveURL(new RegExp(`/tickets/${number}`));
  await expect(b.getByRole("heading", { name: "Anmeldung prüfen", level: 1 })).toBeVisible();
  await expect(b.getByRole("button", { name: "Abgeben" })).toBeVisible();
});

test("a card moved by keyboard and through its menu shows live on the other board", async () => {
  const made = await ticket(anna, space.id, "Board per Tastatur");
  const key = made.key;
  const board = `/spaces/${space.id}/board`;
  const a = await openLive(anna, board);
  const b = await openLive(ben, board);
  await expect(card(column(a, "Neu"), key)).toBeVisible();

  // Ben by keyboard: the grip, Space, Right, Space. The focus stays on the card's grip.
  const grip = card(column(b, "Neu"), key).getByRole("button", { name: `${key} verschieben` });
  // Each step waits for the board's announcement of the one before. The picked-up
  // card listens for keys only from a timer of its own (dnd-kit's keyboard sensor):
  // one turn of the page's timers later, it surely does.
  const told = b.getByRole("status").filter({ hasText: key });
  await grip.focus();
  await b.keyboard.press("Space");
  await expect(told).toHaveText(`${key} über Neu.`);
  await b.evaluate(() => new Promise((resolve) => setTimeout(resolve)));
  await b.keyboard.press("ArrowRight");
  await expect(told).toHaveText(`${key} über In Arbeit.`);
  await b.keyboard.press("Space");
  await expect(told).toHaveText(`${key} in In Arbeit abgelegt.`);
  const moved = card(column(b, "In Arbeit"), key);
  await expect(moved).toBeVisible();
  await expect(moved.getByRole("button", { name: `${key} verschieben` })).toBeFocused();
  await expect(card(column(a, "In Arbeit"), key)).toBeVisible(); // live at Anna's
  await expect(card(column(a, "Neu"), key)).toHaveCount(0);

  // Anna through the card's menu, by keyboard too.
  const menu = card(a, key).getByRole("button", { name: `Status von ${key} ändern` });
  await menu.focus();
  await a.keyboard.press("Enter");
  await a.getByRole("menuitemradio", { name: "Zur Prüfung" }).focus();
  await a.keyboard.press("Enter");
  await expect(card(column(a, "Zur Prüfung"), key)).toBeVisible();
  await expect(
    card(column(a, "Zur Prüfung"), key).getByRole("button", { name: `Status von ${key} ändern` }),
  ).toBeFocused();
  await expect(card(column(b, "Zur Prüfung"), key)).toBeVisible(); // live at Ben's
});

test("a stale tab's move is refused, the card returns and the board says why", async () => {
  const made = await ticket(anna, space.id, "Veraltete Karte");
  const b = await ben.newPage();
  await b.route("**/api/stream", (route) => route.abort()); // this tab hears nothing live
  await b.goto(`/spaces/${space.id}/board`);
  await expect(card(column(b, "Neu"), made.key)).toBeVisible();

  const active = await status(anna, space.id, "In Arbeit");
  await change(anna, made.number, { status_id: active.id }); // elsewhere, meanwhile

  await card(b, made.key)
    .getByRole("button", { name: `Status von ${made.key} ändern` })
    .click();
  await b.getByRole("menuitemradio", { name: "Erledigt" }).click();
  await expect(b.getByRole("alert")).toContainText("inzwischen geändert");
  // Reloaded: the card stands where the other change put it, not where it was dropped.
  await expect(card(column(b, "In Arbeit"), made.key)).toBeVisible();
  await expect(card(column(b, "Erledigt"), made.key)).toHaveCount(0);
});

test("two tabs change the title: the later save gets a conflict and keeps the text", async () => {
  const made = await ticket(anna, space.id, "Titel am Anfang");
  const one = await openLive(ben, `/tickets/${made.number}`);
  const two = await openLive(ben, `/tickets/${made.number}`);

  await one.getByRole("button", { name: "Titel ändern" }).click();
  await one.getByRole("textbox", { name: "Titel" }).fill("Titel aus Tab eins");
  await two.getByRole("button", { name: "Titel ändern" }).click();
  await two.getByRole("textbox", { name: "Titel" }).fill("Titel aus Tab zwei");
  await two.getByRole("button", { name: "Speichern" }).click();
  await expect(two.getByRole("heading", { name: "Titel aus Tab zwei", level: 1 })).toBeVisible();

  await one.getByRole("button", { name: "Speichern" }).click();
  await expect(one.getByText("Jemand hat diesen Eintrag inzwischen geändert.")).toBeVisible();
  await one.getByRole("button", { name: "Aktuelle Fassung laden" }).click();
  // The notice goes once the reload has the current version; saving before that would
  // send the old one again (and the reload's reset would hide that second conflict).
  await expect(one.getByText("Jemand hat diesen Eintrag inzwischen geändert.")).toBeHidden();
  await expect(one.getByRole("textbox", { name: "Titel" })).toHaveValue("Titel aus Tab eins");
  await one.getByRole("button", { name: "Speichern" }).click();
  await expect(one.getByRole("heading", { name: "Titel aus Tab eins", level: 1 })).toBeVisible();
  await expect(two.getByRole("heading", { name: "Titel aus Tab eins", level: 1 })).toBeVisible();
});
