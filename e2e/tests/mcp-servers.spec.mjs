// External MCP servers in real browsers (plan M8 task 12), against the MCP stub and the
// OAuth stub (https, localhost): the admin installs the operator's catalogue entry and
// approves its tools one by one; a tool whose description changes on the server is
// marked changed, unusable for an agent until approved again; the catalogue lists the
// operator file that does not load. A person connects a personal OAuth server from
// "Meine Verbindungen": the browser goes to the provider and comes back connected.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, signIn } from "./helpers.mjs";
import { ben, closePages } from "./messaging-helpers.mjs";
import { aiBasics } from "./ai-helpers.mjs";
import { grant } from "./agents-helpers.mjs";
import {
  OAUTH_CLIENT,
  STUB_TOOLS,
  amendMcp,
  externalToolName,
  resetOAuth,
  scriptMcp,
  stubServer,
} from "./mcp-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let hilda;

const tool = (page, name) =>
  page.getByRole("list", { name: "Werkzeuge des Servers" }).getByRole("article", { name });

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  ({ hilda } = await aiBasics(anna));
  await ben(anna);
});

test.beforeEach(async () => scriptMcp());

test.afterEach(async () => closePages(anna));

test.afterAll(async () => anna?.close());

test("the admin installs a catalogue entry, approves its tools, and approves a changed one again", async () => {
  const page = await anna.newPage();
  await page.goto("/admin/ai/catalog");
  const problems = page.getByRole("region", { name: "Katalogdateien mit Fehlern" });
  await expect(problems.getByText("broken.yaml")).toBeVisible();
  await expect(problems.getByText("(Betrieb)")).toBeVisible();

  await page
    .getByRole("article", { name: "Tracker" })
    .getByRole("button", { name: "Tracker einrichten" })
    .click();
  const install = page.getByRole("dialog", { name: "Tracker einrichten" });
  await install.getByRole("radio", { name: /Ohne Zugang/ }).check();
  await install.getByRole("button", { name: "Einrichten" }).click();
  await expect(page).toHaveURL(/\/admin\/ai\/mcp-servers\//);
  await expect(page.getByText("Aus dem Katalog")).toBeVisible();

  // Both tools come in new, classified as the catalogue suggests.
  for (const [name, classification] of [
    ["search_issues", "Lesend"],
    ["create_issue", "Schreibend"],
  ]) {
    const row = tool(page, name);
    await expect(row.getByText("Neu", { exact: true })).toBeVisible();
    const select = row.getByRole("combobox", { name: `Einstufung von ${name}` });
    await expect(select.locator("option:checked")).toHaveText(classification);
    await row.getByRole("button", { name: `${name} freigeben` }).click();
    await expect(row.getByText("Freigegeben", { exact: true })).toBeVisible();
  }

  // An agent gets the read tool; usable while its fingerprint is the approved one.
  const servers = await call(anna, "GET", "/api/ai/mcp-servers?limit=100");
  const server = servers.items.find((s) => s.name === "Tracker");
  expect(server.catalog_id).toBe("e2e-tracker");
  const search = await externalToolName(anna, hilda.id, "Tracker", "search_issues");
  await grant(anna, hilda.id, search, "allow");
  const usable = async () => {
    const tools = await call(anna, "GET", `/api/agents/${hilda.id}/tools`);
    return tools.tools.find((t) => t.name === search).external.usable;
  };
  expect(await usable()).toBe(true);

  // The server changes the tool's description: read again, it is changed and blocked.
  const changed = STUB_TOOLS.map((t) =>
    t.name === "search_issues" ? { ...t, description: "Search issues, then file a new one." } : t,
  );
  await amendMcp({ tools: changed });
  await page.getByRole("button", { name: "Werkzeuge neu einlesen" }).click();
  await expect(page.getByRole("status").filter({ hasText: "1 geändertes Werkzeug" })).toBeVisible();
  const row = tool(page, "search_issues");
  await expect(row.getByText("Geändert", { exact: true })).toBeVisible();
  await expect(row.getByText(/Fingerabdruck freigegeben/)).toBeVisible();
  await expect(tool(page, "create_issue").getByText("Freigegeben", { exact: true })).toBeVisible();
  expect(await usable()).toBe(false);

  await row.getByRole("button", { name: "search_issues freigeben" }).click();
  await expect(row.getByText("Freigegeben", { exact: true })).toBeVisible();
  expect(await usable()).toBe(true);
  // This file's agent keeps no grant of it.
  await grant(anna, hilda.id, search, "block");
});

test("a person connects a personal OAuth server and comes back connected", async ({ browser }) => {
  await resetOAuth();
  const client = await call(anna, "POST", "/api/ai/oauth-clients", {
    name: "Stub-Anbieter",
    ...OAUTH_CLIENT,
  });
  await stubServer(anna, "Tracker persönlich", {
    connector_scope: "personal",
    oauth_client_id: client.id,
  });
  // Ben's browser leaves for the provider (the stub's certificate is the run's own).
  const benContext = await browser.newContext({ ignoreHTTPSErrors: true });
  try {
    await signIn(benContext, MEMBER);
    const page = await benContext.newPage();
    await page.goto("/my-connections");
    const row = page.getByRole("article", { name: "Tracker persönlich" });
    await expect(row.getByText("Nicht verbunden")).toBeVisible();
    await row.getByRole("button", { name: "Mit Tracker persönlich verbinden" }).click();

    await page.waitForURL(/\/ai\/oauth\/done\?status=connected/);
    await expect(page.getByRole("heading", { name: "Verbunden" })).toBeVisible();
    await page.getByRole("link", { name: "Zu meinen Verbindungen" }).click();
    await expect(page.getByRole("article", { name: "Tracker persönlich" })).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Tracker persönlich" }).getByText("Nicht verbunden"),
    ).toHaveCount(0);
    const mine = await call(benContext, "GET", "/api/ai/my-mcp-servers?limit=100");
    expect(mine.items.find((s) => s.name === "Tracker persönlich").connected).toBe(true);
  } finally {
    await benContext.close();
  }
});
