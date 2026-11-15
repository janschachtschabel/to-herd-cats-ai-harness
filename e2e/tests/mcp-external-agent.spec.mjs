// An external agent in real browsers (plan M8 task 12): the admin creates it and its
// token in the UI (clear text once); a ticket assigned to it shows "Wartet auf
// Abholung"; a script with the agent's token picks the ticket up over `/mcp`
// (`list_my_tickets`, `claim_ticket`), comments and moves it to review, and the
// ticket shows it live with the agent as author; "Erledigt" is refused. A mention of
// the agent in a channel starts nothing and says why.
import { expect, test } from "@playwright/test";
import { OWNER, call, signIn } from "./helpers.mjs";
import { channel, closePages, composer, message, openLive } from "./messaging-helpers.mjs";
import { member } from "./agents-helpers.mjs";
import { aiBasics } from "./ai-helpers.mjs";
import { change, discussion, status, ticket } from "./tickets-helpers.mjs";
import { mcpSwitch, mcpTool, mcpTools } from "./mcp-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let yard;
let kodex;
let secret;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  // Assigning a ticket to an agent, external ones too, needs `ai.use`.
  await aiBasics(anna);
  await mcpSwitch(anna, true);
  yard = await call(anna, "POST", "/api/spaces", { name: "Werft", kind: "team" });
});

test.afterEach(async () => closePages(anna));

test.afterAll(async () => {
  if (anna) await mcpSwitch(anna, false);
  await anna?.close();
});

test("the admin creates an external agent and its token in the UI", async () => {
  const page = await anna.newPage();
  await page.goto("/admin/agents");
  await page.getByRole("button", { name: "Externen Agenten anlegen" }).click();
  const dialog = page.getByRole("dialog", { name: "Externen Agenten anlegen" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Kodex");
  await dialog.getByRole("radio", { name: /Stufe 2/ }).check();
  await dialog.getByRole("combobox", { name: "Status" }).selectOption({ label: "Aktiv" });
  await dialog.getByRole("button", { name: "Anlegen" }).click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole("article", { name: "Kodex" });
  await expect(card.getByText("Extern über MCP")).toBeVisible();
  const list = await call(anna, "GET", "/api/agents?limit=100");
  kodex = list.items.find((a) => a.name === "Kodex");
  expect(kodex).toMatchObject({ kind: "external", level: 2, status: "active" });
  await member(anna, yard.id, { type: "agent", id: kodex.id }, "editor");

  await card.getByRole("link", { name: "Stufe, Werkzeuge, Token" }).click();
  const tokens = page.getByRole("region", { name: "Token des Agenten" });
  await expect(tokens.getByText("Kodex hat noch kein Token.")).toBeVisible();
  await tokens.getByRole("button", { name: "Token anlegen" }).click();
  const create = page.getByRole("dialog", { name: "Zugangstoken anlegen" });
  await create.getByRole("textbox", { name: "Name" }).fill("Werft-Pipeline");
  await create.getByRole("radio", { name: /Lesen und schreiben/ }).check();
  await create.getByRole("spinbutton", { name: "Gültig (Tage)" }).fill("7");
  await create.getByRole("button", { name: "Anlegen" }).click();
  const shown = page.getByRole("dialog", { name: "Dein neues Token: Werft-Pipeline" });
  secret = await shown.getByRole("textbox", { name: "Token" }).inputValue();
  expect(secret).toMatch(/^herd_agt_/);
  await expect(shown.getByText(/list_my_tickets/).first()).toBeVisible();
  await shown.getByRole("button", { name: "Fertig" }).click();
  await expect(tokens.getByRole("article", { name: "Werft-Pipeline" })).toBeVisible();
  expect(await page.content()).not.toContain(secret);

  const offered = await mcpTools(anna.request, secret);
  expect(offered).toEqual(expect.arrayContaining(["claim_ticket", "list_my_tickets"]));
  expect(offered).not.toContain("assign_ticket");
});

test("a script with the agent's token picks a ticket up and brings it to review; done is refused", async () => {
  const hull = await ticket(anna, yard.id, "Rumpf streichen");
  await change(anna, hull.number, { assignee: { type: "agent", id: kodex.id } });
  const review = await status(anna, yard.id, "Zur Prüfung");
  const active = await status(anna, yard.id, "In Arbeit");
  const page = await openLive(anna, `/tickets/${hull.number}`);
  const pickup = page.getByText("Wartet auf Abholung");
  await expect(pickup).toBeVisible();

  const mine = await mcpTool(anna.request, secret, "list_my_tickets");
  expect(mine.text).toContain(hull.key);
  const claimed = await mcpTool(anna.request, secret, "claim_ticket", { key: hull.key });
  expect(claimed.isError, claimed.text).toBe(false);
  await expect(pickup).toBeHidden();
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveValue(active.id);

  await mcpTool(anna.request, secret, "comment_ticket", {
    key: hull.key,
    text: "Grundiert und zweimal gestrichen.",
  });
  const moved = await mcpTool(anna.request, secret, "set_ticket_status", {
    key: hull.key,
    status: review.name,
  });
  expect(moved.isError, moved.text).toBe(false);
  const comment = message(discussion(page), "Kodex", "Grundiert und zweimal gestrichen.");
  await expect(comment).toBeVisible();
  await expect(comment.getByText("Von einer KI geschrieben")).toBeAttached();
  await expect(comment.getByText("über Token „Werft-Pipeline“")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveValue(review.id);

  // Done is a person's: refused as a tool error, the ticket stays in review.
  const done = await mcpTool(anna.request, secret, "set_ticket_status", {
    key: hull.key,
    status: "Erledigt",
  });
  expect(done.isError).toBe(true);
  const now = await call(anna, "GET", `/api/tickets/${hull.number}`);
  expect(now.status.category).toBe("review");
  expect(now.assignee).toMatchObject({ type: "agent", id: kodex.id });
  expect(now.awaiting_pickup).toBe(false);
});

test("a mention of the external agent in a channel starts nothing and says why", async () => {
  const room = await channel(anna, yard.id, "werft");
  const page = await openLive(anna, `/c/${room.id}`);
  const box = composer(page, "Nachricht an #werft");
  await box.pressSequentially("@Kod");
  const option = page
    .getByRole("listbox", { name: "Person erwähnen" })
    .getByRole("option", { name: /Kodex/ });
  await expect(option.getByText("extern", { exact: true })).toBeVisible();
  await option.click();
  await box.pressSequentially("streichst du auch das Deck?");
  await box.press("Enter");
  await expect(message(page, "anna", "streichst du auch das Deck?")).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: /arbeitet von außen über MCP/ }),
  ).toBeVisible();
  const runs = await call(anna, "GET", `/api/runs?agent_id=${kodex.id}&limit=10`);
  expect(runs.items).toEqual([]);
});
