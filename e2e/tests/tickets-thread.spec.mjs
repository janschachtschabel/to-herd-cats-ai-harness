// Tickets in real browsers (plan M4, task 8), part two: a ticket's discussion with the
// worker's grey timeline, which can be hidden; a ticket key in a channel shows a card to
// a member and plain text to a person without access, who cannot open the ticket either;
// a page link shows from the ticket and from the page.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";
import {
  CLARA,
  channel,
  closePages,
  message,
  openLive,
  person,
  post,
  send,
} from "./messaging-helpers.mjs";
import { change, discussion, openSpace, status, ticket } from "./tickets-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let clara;
let space;
let benId;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  clara = await browser.newContext();
  await signIn(anna, OWNER);
  space = await teamSpace(anna, "Projekt Birne"); // makes Ben, an editor here
  await person(anna, CLARA); // in the organisation, not in the space
  benId = (await signIn(ben, MEMBER)).id;
  await signIn(clara, CLARA);
});

test.afterEach(async () => closePages(anna, ben, clara));

test.afterAll(async () => {
  for (const context of [anna, ben, clara]) await context?.close();
});

test("the ticket's discussion holds comments and the timeline, which can be hidden", async () => {
  const made = await ticket(anna, space.id, "Druckerpapier bestellen", {
    assignee: { type: "user", id: benId },
  });
  await change(anna, made.number, { priority: "high" });

  const b = await openLive(ben, `/tickets/${made.number}`);
  const panel = discussion(b);
  await expect(panel.getByText("anna hat das Ticket angelegt.")).toBeVisible();
  await expect(panel.getByText("anna hat das Ticket Ben zugewiesen.")).toBeVisible();
  await expect(
    panel.getByText("anna hat die Priorität von Normal auf Hoch geändert."),
  ).toBeVisible();

  await send(panel, "Kommentar schreiben", "Welche Grammatur brauchen wir?");
  await expect(message(panel, "Ben", "Welche Grammatur brauchen wir?")).toBeVisible();
  const a = await openLive(anna, `/tickets/${made.number}`);
  await expect(message(discussion(a), "Ben", "Welche Grammatur")).toBeVisible();

  // Anna moves it on; the entry arrives live at Ben's, beside his comment.
  const active = await status(anna, space.id, "In Arbeit");
  await change(anna, made.number, { status_id: active.id });
  const moved = "anna hat den Status von Neu auf In Arbeit gesetzt.";
  await expect(panel.getByText(moved)).toBeVisible();

  await panel.getByRole("checkbox", { name: "Systemmeldungen ausblenden" }).check();
  await expect(panel.getByText(moved)).toBeHidden();
  await expect(panel.getByText("anna hat das Ticket angelegt.")).toBeHidden();
  await expect(message(panel, "Ben", "Welche Grammatur brauchen wir?")).toBeVisible();
  await panel.getByRole("checkbox", { name: "Systemmeldungen ausblenden" }).uncheck();
  await expect(panel.getByText(moved)).toBeVisible();
});

test("a ticket key in a channel: a card for a member, plain text for anyone else", async () => {
  const made = await ticket(anna, space.id, "Schlüssel tauschen");
  const house = await openSpace(anna, "Haus");
  const room = await channel(anna, house.id, "flur");
  await post(anna, room.id, `Bitte ${made.key} ansehen, Details unter /tickets/${made.number}.`);
  const label = `Ticket ${made.key}: Schlüssel tauschen`;

  const b = await openLive(ben, `/c/${room.id}`);
  const forBen = message(b, "anna", "Bitte");
  await expect(forBen.getByRole("link", { name: label })).toHaveCount(1); // key and link: one card
  await expect(forBen.getByRole("link", { name: label })).toContainText("Neu");
  // The card keeps itself current.
  const active = await status(anna, space.id, "In Arbeit");
  await change(anna, made.number, { status_id: active.id });
  await expect(forBen.getByRole("link", { name: label })).toContainText("In Arbeit");

  // Clara reads the channel but not the space: the text, no card (its load answered 404).
  const c = await clara.newPage();
  const refused = c.waitForResponse(
    (r) => new URL(r.url()).pathname === `/api/tickets/${made.number}` && r.status() === 404,
  );
  await c.goto(`/c/${room.id}`);
  const forClara = message(c, "anna", `Bitte ${made.key} ansehen`);
  await expect(forClara).toBeVisible();
  await refused;
  await expect(forClara.getByRole("link", { name: /^Ticket / })).toHaveCount(0);
  await expect(c.getByText("Schlüssel tauschen")).toHaveCount(0);

  // Opening it gives the same view as a number that does not exist.
  await c.goto(`/tickets/${made.number}`);
  const gone = "Dieses Ticket gibt es nicht, oder du darfst es nicht sehen.";
  await expect(c.getByText(gone)).toBeVisible();
  await c.goto("/tickets/999999");
  await expect(c.getByText(gone)).toBeVisible();
  for (const number of [made.number, 999999]) {
    const r = await clara.request.get(`/api/tickets/${number}`);
    expect(r.status()).toBe(404);
    expect((await r.json()).error.code).toBe("ticket.not_found");
  }
});

test("a page linked from the ticket shows on the page and unlinks from there", async () => {
  const doc = await publishedPage(anna, space.id, "Lieferanten", "Wer liefert was.");
  const made = await ticket(anna, space.id, "Lieferanten anschreiben");

  const b = await openLive(ben, `/tickets/${made.number}`);
  const pages = b.getByRole("region", { name: "Verknüpfte Seiten" });
  await expect(pages).toContainText("Keine");
  await b.getByRole("button", { name: "Seite verknüpfen" }).click();
  const pick = b.getByRole("dialog", { name: "Seite verknüpfen" });
  await pick.getByRole("combobox", { name: "Suchen" }).fill("Lieferanten");
  await expect(pick.getByRole("option", { name: /Lieferanten/ })).toBeVisible();
  await b.keyboard.press("Enter");
  await expect(pick).toBeHidden();
  await expect(pages.getByRole("link", { name: "Lieferanten" })).toBeVisible();
  await expect(discussion(b).getByText("Ben hat die Seite „Lieferanten“ verknüpft.")).toBeVisible();

  // On the page, for Anna: the ticket under "linked tickets"; she unlinks it there.
  const a = await openLive(anna, pageUrl(space, doc));
  const linked = a.getByRole("region", { name: "Verknüpfte Tickets" });
  await expect(linked).toContainText(made.key);
  await expect(linked).toContainText("Lieferanten anschreiben");
  await linked.getByRole("button", { name: `Verknüpfung mit ${made.key} lösen` }).click();
  await expect(linked).toContainText("Noch keine Tickets mit dieser Seite verknüpft.");

  // Live back at the ticket: the link is gone, the timeline says who removed it.
  await expect(pages).toContainText("Keine");
  await expect(
    discussion(b).getByText("anna hat die Verknüpfung mit „Lieferanten“ gelöst."),
  ).toBeVisible();
  const left = await call(ben, "GET", `/api/tickets/${made.number}/pages`);
  expect(left.items).toEqual([]);
});
