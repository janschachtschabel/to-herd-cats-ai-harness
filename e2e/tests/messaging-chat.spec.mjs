// Messaging in real browsers (plan M3, task 12): two people in one channel see each
// other's messages, reactions and thread replies live (outbox → worker → NOTIFY → SSE);
// a mention reaches the other person's activity; the search finds a message and opens
// the conversation at it. The app runs in role all, so its worker delivers the events.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, signIn, teamSpace } from "./helpers.mjs";
import {
  channel,
  closePages,
  composer,
  message,
  openLive,
  post,
  send,
} from "./messaging-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let space;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER);
  space = await teamSpace(anna, "Nachrichten"); // makes Ben, an editor here
  await signIn(ben, MEMBER);
});

test.afterEach(async () => closePages(anna, ben));

test.afterAll(async () => {
  await anna?.close();
  await ben?.close();
});

test("two people in a channel see each other's messages, reactions and replies live", async () => {
  const room = await channel(anna, space.id, "projekt");
  const a = await openLive(anna, `/c/${room.id}`);
  const b = await openLive(ben, `/c/${room.id}`);
  await expect(b.getByText("Noch keine Nachrichten. Schreib die erste!")).toBeVisible();

  await send(a, "Nachricht an #projekt", "Hallo Ben, der Plan steht.");
  const fromAnna = message(b, "anna", "Hallo Ben, der Plan steht.");
  await expect(fromAnna).toBeVisible();
  await send(b, "Nachricht an #projekt", "Danke, Anna!");
  await expect(message(a, "Ben", "Danke, Anna!")).toBeVisible();

  // A reaction arrives live.
  await fromAnna.hover();
  await fromAnna.getByRole("button", { name: "Reaktion hinzufügen" }).click();
  await b.getByRole("menuitem", { name: "Mit 👍 reagieren" }).click();
  await expect(
    message(a, "anna", "Hallo Ben").getByRole("button", { name: "👍: 1 Reaktion" }),
  ).toBeVisible();

  // A reply in the thread: Anna sees the count live and opens the thread.
  await fromAnna.hover();
  await fromAnna.getByRole("button", { name: "Im Thread antworten" }).click();
  const thread = b.getByRole("complementary", { name: "Thread" });
  await send(thread, "Im Thread antworten", "Ich übernehme Teil zwei.");
  await expect(message(thread, "Ben", "Ich übernehme Teil zwei.")).toBeVisible();
  const open = a.getByRole("button", { name: "Thread von anna öffnen, 1 Antwort" });
  await expect(open).toBeVisible();
  await open.click();
  await expect(
    message(a.getByRole("complementary", { name: "Thread" }), "Ben", "Ich übernehme Teil zwei."),
  ).toBeVisible();
});

test("a mention shows up in the other person's activity", async () => {
  const room = await channel(anna, space.id, "planung");
  const b = await openLive(ben, "/activity");
  await expect(b.getByRole("heading", { name: "Aktivität" })).toBeVisible();
  const a = await openLive(anna, `/c/${room.id}`);

  const box = composer(a, "Nachricht an #planung");
  await box.pressSequentially("@Be");
  await a
    .getByRole("listbox", { name: "Person erwähnen" })
    .getByRole("option", { name: "Ben" })
    .click();
  await box.pressSequentially("bitte die Liste prüfen");
  await box.press("Enter");
  await expect(message(a, "anna", "bitte die Liste prüfen")).toBeVisible();

  // Live: the counter in the sidebar and the entry in the open activity view.
  await expect(b.getByRole("link", { name: /^Aktivität \d+ ungelesene?r? Eintr/ })).toBeVisible();
  const entry = b.getByRole("listitem").filter({ hasText: "bitte die Liste prüfen" });
  await expect(entry).toContainText("anna hat dich in");
  await entry.getByRole("button", { name: "Öffnen" }).click();
  await expect(b).toHaveURL(new RegExp(`/c/${room.id}`));
  await expect(message(b, "anna", "bitte die Liste prüfen")).toBeVisible();
});

test("the search finds a message and opens the conversation at it", async () => {
  const room = await channel(anna, space.id, "suche");
  const found = await post(anna, room.id, "Der Zitronenfalter kommt in die Doku.");
  await post(anna, room.id, "Etwas anderes.");

  const b = await openLive(ben, "/");
  await b.keyboard.press("Control+k");
  await b.getByRole("combobox", { name: "Suchbegriff" }).fill("Zitronenfalter");
  const hit = b.getByRole("option").filter({ hasText: "von anna" });
  await expect(hit).toContainText("Zitronenfalter");
  await hit.click();
  await expect(b).toHaveURL(new RegExp(`/c/${room.id}.*message=${found.id}`));
  await expect(message(b, "anna", "Zitronenfalter")).toBeVisible();
});
