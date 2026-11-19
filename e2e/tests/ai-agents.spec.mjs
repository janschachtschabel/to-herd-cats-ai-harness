// AI and agents in real browsers (plan M5, task 7), with the OpenAI stub as the only
// provider (no network): the admin sets up a connection, assigns AI and creates an
// agent in the UI; a person talks to the agent in a direct message, sees its progress
// and its answer with the AI mark; a person without AI sees no AI anywhere; a
// restricted page read over an external connection stops the run (`policy_blocked`)
// and the conversation says so; a paused agent is worded on sending. The app runs in
// role all, so its worker runs the agent.
import { expect, test } from "@playwright/test";
import { OWNER, call, publishedPage, signIn } from "./helpers.mjs";
import { CLARA, closePages, composer, openLive, person, send } from "./messaging-helpers.mjs";
import { STUB_API, agent, aiBasics, scriptStub, stubConnection, stubLog } from "./ai-helpers.mjs";

test.describe.configure({ mode: "serial" });

const DM_COMPOSER = "Nachricht an Direktnachricht";
// A person of this file alone, so its direct messages with agents never show up in
// the other files' lists (one database per run).
const DORA = { email: "dora@e2e.example", password: "e2e-password-321", name: "Dora" };
let anna;
let doraContext;

const agentAnswer = (page, name, text) =>
  page.getByRole("article", { name: `Nachricht von ${name}` }).filter({ hasText: text });

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  doraContext = await browser.newContext();
  await signIn(anna, OWNER);
  await person(anna, DORA);
  await signIn(doraContext, DORA);
});

test.beforeEach(async () => scriptStub(anna.request));

test.afterEach(async () => closePages(anna, doraContext));

test.afterAll(async () => {
  await anna?.close();
  await doraContext?.close();
});

test("the admin sets up AI and an agent; a person asks it and gets an answer marked as AI", async () => {
  const admin = await anna.newPage();
  await admin.goto("/admin/ai");
  await expect(admin.getByText(/Noch keine Verbindung eingerichtet/)).toBeVisible();
  await admin.getByRole("button", { name: "Verbindung einrichten" }).first().click();
  const setup = admin.getByRole("dialog");
  await setup.getByLabel("Name", { exact: true }).fill("Stub");
  await setup.getByLabel("Art", { exact: true }).selectOption("local");
  await setup.getByLabel("Adresse (Basis-URL)").fill(STUB_API);
  await setup.getByLabel("Schlüssel (wird verschlüsselt gespeichert)").fill("sk-e2e-not-real");
  await setup.getByLabel("Modelle").fill("gpt-6-luna");
  await setup.getByLabel("Datenort").selectOption("local");
  await setup.getByRole("button", { name: "Einrichten" }).click();
  const card = admin.getByRole("article", { name: "Stub" });
  await expect(card.getByText("Verschlüsselt gespeichert")).toBeVisible();
  await expect(admin.getByText("sk-e2e-not-real")).toHaveCount(0);
  await card.getByRole("button", { name: "Testen" }).click();
  await expect(card.getByRole("status")).toHaveText(/Verbindung funktioniert \(gpt-6-luna/);

  await admin.getByRole("link", { name: "Zuordnung" }).click();
  const standard = admin.getByRole("region", { name: "Standard der Organisation" });
  await standard.getByLabel("Verbindung").selectOption({ label: "Stub" });
  await standard.getByRole("button", { name: "Speichern" }).click();
  await expect(standard.getByRole("status")).toHaveText("Gespeichert.");

  // Saving the standard gives Anna AI too, so once /auth/me is fetched again her
  // sidebar also shows "Meine Agenten": name the administration's link exactly.
  await admin.getByRole("link", { name: "Agenten", exact: true }).click();
  await admin.getByRole("button", { name: "Agent anlegen" }).click();
  const form = admin.getByRole("dialog");
  await form.getByLabel("Name", { exact: true }).fill("Hilda");
  await form.getByLabel("Kurzvorstellung").fill("Hilda beantwortet Fragen.");
  await form.getByLabel("Anweisungen").fill("Antworte kurz und auf Deutsch.");
  await form.getByLabel("Status").selectOption("active");
  await form.getByRole("button", { name: "Anlegen" }).click();
  await expect(admin.getByRole("article", { name: "Hilda" }).getByText("Aktiv")).toBeVisible();

  // Dora (AI through the standard) opens a direct message with Hilda from the dialog.
  await scriptStub(anna.request, { delay: 1.5, replies: [{ content: "Es gibt 30 Tage Urlaub." }] });
  const b = await openLive(doraContext, "/spaces");
  await b.getByRole("button", { name: "Direktnachricht beginnen" }).click();
  const dialog = b.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Agent" }).click();
  await dialog.getByRole("option", { name: /Hilda/ }).click();
  await dialog.getByRole("button", { name: "Gespräch öffnen" }).click();
  await expect(b.getByText("Hilda beantwortet Fragen.")).toBeVisible();

  await send(b, DM_COMPOSER, "Wie viele Urlaubstage habe ich?");
  // The run shows its progress while the provider thinks, then the answer stands.
  await expect(b.getByRole("status").filter({ hasText: /Hilda (beginnt|arbeitet)/ })).toBeVisible();
  const answer = agentAnswer(b, "Hilda", "Es gibt 30 Tage Urlaub.");
  await expect(answer).toBeVisible();
  await expect(answer.getByText("Von einer KI geschrieben")).toBeAttached();
  await expect(b.getByRole("status").filter({ hasText: /Hilda (beginnt|arbeitet)/ })).toHaveCount(
    0,
  );
  expect(await stubLog(anna.request)).toContain("Wie viele Urlaubstage habe ich?");
});

test("a person without AI sees no AI entry point anywhere", async ({ browser }) => {
  const { hilda } = await aiBasics(anna);
  const clara = await person(anna, CLARA);
  const assignments = await call(anna, "GET", "/api/ai/assignments/users?limit=100");
  if (!assignments.items.some((a) => a.user_id === clara.id)) {
    await call(anna, "PUT", `/api/ai/assignments/users/${clara.id}`, {
      no_ai: true,
      version: null,
    });
  }
  const context = await browser.newContext();
  try {
    await signIn(context, CLARA);
    const me = await call(context, "GET", "/api/auth/me");
    expect(me.permissions).not.toContain("ai.use");
    const page = await context.newPage();
    await page.goto("/spaces");
    await page.getByRole("button", { name: "Direktnachricht beginnen" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("combobox", { name: "Personen" })).toBeVisible();
    await expect(dialog.getByText("Mit einem Agenten sprechen")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("link", { name: "KI", exact: true })).toHaveCount(0);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Profil" })).toBeVisible();
    await expect(page.getByText("Meine KI")).toHaveCount(0);
    await page.goto("/admin/ai");
    await expect(page.getByRole("heading", { name: "Seite nicht gefunden" })).toBeVisible();
    // The API agrees: no agent, no profile, no usage.
    const agents = await context.request.get("/api/directory?type=agent");
    expect((await agents.json()).items).toEqual([]);
    const profile = await context.request.get(`/api/agents/${hilda.id}/profile`);
    expect(profile.status()).toBe(404);
  } finally {
    await context.close();
  }
});

test("a restricted page read over an external connection stops the run, and the DM says so", async () => {
  await aiBasics(anna);
  const external = await stubConnection(anna, "Extern", "external");
  const rita = await agent(anna, "Rita", external);
  const space = await call(anna, "POST", "/api/spaces", { name: "Vertraulich", kind: "team" });
  const dora = await person(anna, DORA);
  await call(anna, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "user",
    member_id: dora.id,
    role: "editor",
  });
  await call(anna, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "agent",
    member_id: rita.id,
    role: "viewer",
  });
  await call(anna, "PATCH", `/api/spaces/${space.id}`, {
    ai_policy: "restricted",
    allowed_locations: ["eu"],
    version: space.version,
  });
  const secret = await publishedPage(anna, space.id, "Gehaltsbänder", "Kennwort ZEBRA-4711");
  const dm = await call(doraContext, "POST", "/api/dms", { agent_id: rita.id });
  await scriptStub(anna.request, {
    replies: [
      { tool_calls: [{ name: "read_page", arguments: { page_id: secret.id } }] },
      { content: "Das sollte nie gesendet werden." },
    ],
  });

  const b = await openLive(doraContext, `/c/${dm.id}`);
  await send(b, DM_COMPOSER, "Was steht auf der Seite Gehaltsbänder?");
  await expect(b.getByText(/Durch die KI-Richtlinie eines Bereichs gestoppt/)).toBeVisible();
  await expect(agentAnswer(b, "Rita", "Das sollte nie gesendet werden.")).toHaveCount(0);
  // The read page never reached the external connection.
  expect(await stubLog(anna.request)).not.toContain("ZEBRA-4711");
});

test("an agent paused by the admin is worded when one writes to it", async () => {
  const { hilda } = await aiBasics(anna);
  const dm = await call(doraContext, "POST", "/api/dms", { agent_id: hilda.id });
  const admin = await anna.newPage();
  await admin.goto("/admin/agents");
  const card = admin.getByRole("article", { name: "Hilda" });
  await card.getByRole("button", { name: "Pausieren" }).click();
  await expect(card.getByText("Pausiert")).toBeVisible();

  const b = await openLive(doraContext, `/c/${dm.id}`);
  await expect(b.getByText("Dieser Agent ist pausiert und antwortet gerade nicht.")).toBeVisible();
  await send(b, DM_COMPOSER, "Bist du da?");
  await expect(
    b.getByText(
      /Dieser Agent ist pausiert und antwortet gerade nicht. Deine Nachricht ist gespeichert./,
    ),
  ).toBeVisible();
  await expect(composer(b, DM_COMPOSER)).toBeEnabled();
  expect(await stubLog(anna.request)).not.toContain("Bist du da?");
  await agent(anna, "Hilda"); // active again for later runs
});
