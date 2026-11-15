// Access tokens and `/mcp` in real browsers (plan M8 task 12): an admin switches MCP on
// in the UI; a person makes a token in the UI and sees its clear text once; a client
// (plain HTTP from the test, a bearer token) lists the tools and reads only the
// token's spaces, a page elsewhere answering like an unknown one; the revoked token is
// refused. A write token comments a ticket, and the ticket's thread shows the comment
// live with the AI mark and the token's name.
import { expect, test } from "@playwright/test";
import { OWNER, call, publishedPage, signIn } from "./helpers.mjs";
import { closePages, message, openLive } from "./messaging-helpers.mjs";
import { discussion, ticket } from "./tickets-helpers.mjs";
import { apiToken, mcpRequest, mcpSwitch, mcpTool, mcpTools } from "./mcp-helpers.mjs";

test.describe.configure({ mode: "serial" });

const READ_TOOLS = [
  "list_tree",
  "list_versions",
  "read_page",
  "read_ticket",
  "search",
  "search_tickets",
];
const UNKNOWN_PAGE = "01900000-0000-7000-8000-000000000000";
let anna;
let lighthouse; // in the token's scope
let vault; // Anna reads it, the token does not
let beacon;
let plan;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  await mcpSwitch(anna, false);
  lighthouse = await call(anna, "POST", "/api/spaces", { name: "Leuchtturm", kind: "team" });
  vault = await call(anna, "POST", "/api/spaces", { name: "Tresor", kind: "team" });
  beacon = await publishedPage(anna, lighthouse.id, "Leuchtfeuer", "Das Feuer brennt nachts.\n");
  plan = await publishedPage(anna, vault.id, "Geheimplan", "Niemand liest das.\n");
});

test.afterEach(async () => closePages(anna));

test.afterAll(async () => {
  if (anna) await mcpSwitch(anna, false);
  await anna?.close();
});

test("a token made in the UI is shown once, reads only its spaces over /mcp, and is refused once revoked", async () => {
  // The admin switches MCP on.
  const admin = await anna.newPage();
  await admin.goto("/admin/ai/mcp");
  const settings = admin.getByRole("form", { name: "Zugang über MCP" });
  await expect(settings.getByRole("status")).toHaveText(/Ausgeschaltet/);
  await settings.getByRole("checkbox", { name: /Zugangstoken erlauben/ }).check();
  await settings.getByRole("button", { name: "Speichern" }).click();
  await expect(settings.getByRole("status")).toHaveText(/Eingeschaltet/);

  // A token for the lighthouse alone, made in the UI.
  const page = await anna.newPage();
  await page.goto("/profile/tokens");
  await expect(page.getByText("Du hast noch kein Zugangstoken.")).toBeVisible();
  await page.getByRole("button", { name: "Token anlegen" }).click();
  const create = page.getByRole("dialog", { name: "Zugangstoken anlegen" });
  await create.getByRole("textbox", { name: "Name" }).fill("Claude Code Laptop");
  await create.getByRole("radio", { name: /Nur lesen/ }).check();
  await create.getByRole("radio", { name: "Nur ausgewählte Bereiche" }).check();
  await create.getByRole("checkbox", { name: "Leuchtturm" }).check();
  await create.getByRole("spinbutton", { name: "Gültig (Tage)" }).fill("7");
  await create.getByRole("button", { name: "Anlegen" }).click();

  const shown = page.getByRole("dialog", { name: "Dein neues Token: Claude Code Laptop" });
  await expect(shown.getByText(/nur dieses eine Mal angezeigt/)).toBeVisible();
  const secret = await shown.getByRole("textbox", { name: "Token" }).inputValue();
  expect(secret).toMatch(/^herd_pat_/);
  await expect(shown.getByText(/claude mcp add/)).toBeVisible();
  await shown.getByRole("button", { name: "Fertig" }).click();
  await expect(shown).toBeHidden();
  const row = page.getByRole("article", { name: "Claude Code Laptop" });
  await expect(row.getByText("Aktiv")).toBeVisible();
  await expect(row.getByText("Leuchtturm")).toBeVisible();
  // Once closed, the clear text is gone: not in the page, not after a reload, not in the API.
  expect(await page.content()).not.toContain(secret);
  await page.reload();
  await expect(row).toBeVisible();
  expect(await page.content()).not.toContain(secret);
  expect(JSON.stringify(await call(anna, "GET", "/api/tokens?limit=100"))).not.toContain(secret);

  // A client with it: the read tools, the lighthouse's page, nothing of the vault.
  const client = anna.request;
  expect(await mcpTools(client, secret)).toEqual(READ_TOOLS);
  const read = await mcpTool(client, secret, "read_page", { page_id: beacon.id });
  expect(read.isError).toBe(false);
  expect(read.text).toContain("Das Feuer brennt nachts.");
  const hidden = await mcpTool(client, secret, "read_page", { page_id: plan.id });
  const unknown = await mcpTool(client, secret, "read_page", { page_id: UNKNOWN_PAGE });
  expect(hidden.text.replace(plan.id, "ID")).toBe(unknown.text.replace(UNKNOWN_PAGE, "ID"));
  expect(hidden.text).not.toContain("Niemand liest das.");
  const found = await mcpTool(client, secret, "search", { query: "Geheimplan" });
  expect(found.text).not.toContain("Geheimplan");
  expect((await mcpTool(client, secret, "search", { query: "Leuchtfeuer" })).text).toContain(
    "Leuchtfeuer",
  );

  // The calls are listed for the token (tool and outcome, no content).
  await row.getByRole("button", { name: "Aufrufe von Claude Code Laptop" }).click();
  const calls = page.getByRole("dialog", { name: /Aufrufe von Claude Code Laptop/ });
  await expect(calls.getByRole("list", { name: "Aufrufe" }).getByRole("listitem")).toHaveCount(5);
  await expect(calls.getByText("read_page").first()).toBeVisible();
  await calls.press("Escape");

  // Revoked in the UI, the token answers like an unknown one.
  await row.getByRole("button", { name: "Claude Code Laptop widerrufen" }).click();
  await page
    .getByRole("dialog", { name: "Token widerrufen?" })
    .getByRole("button", { name: "Widerrufen" })
    .click();
  await expect(row.getByText("Widerrufen", { exact: true }).first()).toBeVisible();
  const refused = await mcpRequest(client, secret, "tools/list");
  const stranger = await mcpRequest(client, `herd_pat_${"x".repeat(43)}`, "tools/list");
  expect(refused.status).toBe(401);
  expect(refused.body.error.data.code).toBe("token.invalid");
  expect(stranger.status).toBe(401);
  expect(refused.body.error.data.message).toBe(stranger.body.error.data.message);
});

test("a write token comments a ticket over /mcp; the thread shows it live with the token's mark", async () => {
  await mcpSwitch(anna, true);
  const made = await apiToken(anna, "Pipeline-Skript", "write", [lighthouse.id]);
  const lamp = await ticket(anna, lighthouse.id, "Lampe tauschen");
  const locked = await ticket(anna, vault.id, "Tresor ölen");
  const page = await openLive(anna, `/tickets/${lamp.number}`);
  await expect(discussion(page)).toBeVisible();

  const written = await mcpTool(anna.request, made.secret, "comment_ticket", {
    key: lamp.key,
    text: "Die Lampe ist bestellt.",
  });
  expect(written.isError).toBe(false);
  const comment = message(discussion(page), "anna", "Die Lampe ist bestellt.");
  await expect(comment).toBeVisible();
  await expect(comment.getByText("Von einer KI geschrieben")).toBeAttached();
  await expect(comment.getByText("über Token „Pipeline-Skript“")).toBeVisible();

  // A ticket outside the token's spaces is not there for it, and nothing is written.
  const outside = await mcpTool(anna.request, made.secret, "comment_ticket", {
    key: locked.key,
    text: "Darf nicht ankommen.",
  });
  expect(outside.isError).toBe(true);
  const thread = await call(anna, "GET", `/api/tickets/${locked.number}/thread`);
  const there = await call(anna, "GET", `/api/conversations/${thread.id}/messages?limit=100`);
  expect(JSON.stringify(there.items)).not.toContain("Darf nicht ankommen.");
});
