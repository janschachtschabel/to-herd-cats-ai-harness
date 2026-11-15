// Proposals and skills in real browsers (plan M6, task 11): a moderator accepts an
// agent's proposal and the page shows it; a proposal whose page moved on opens the
// merge dialog, where a conflict is decided and the merged text accepted; the admin
// imports a SKILL.md and assigns it to an agent; a person without AI sees no skills
// anywhere. Proposals are made through the backend's service (`seedProposal`: agents
// propose from their runs, there is no public route).
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { OWNER, call, pageUrl, publishedPage, signIn } from "./helpers.mjs";
import { person } from "./messaging-helpers.mjs";
import { aiBasics, seedProposal } from "./ai-helpers.mjs";

test.describe.configure({ mode: "serial" });

// A person of this file alone, without AI.
const EMIL = { email: "emil@e2e.example", password: "e2e-password-654", name: "Emil" };
let anna;
let hilda;
let space;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  ({ hilda } = await aiBasics(anna));
  space = await call(anna, "POST", "/api/spaces", { name: "Handbuch", kind: "team" });
  await call(anna, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "agent",
    member_id: hilda.id,
    role: "editor",
  });
});

test.afterAll(async () => anna?.close());

const proposalLink = (page, title) =>
  page
    .getByRole("list", { name: "Vorschläge" })
    .getByRole("link", { name: `Änderung an „${title}“` });

test("a moderator accepts an agent's proposal and the page shows the change", async () => {
  const doc = await publishedPage(anna, space.id, "Urlaub", "Es gibt 28 Tage Urlaub.\n");
  seedProposal({
    email: OWNER.email,
    agentId: hilda.id,
    pageId: doc.id,
    content: "Es gibt 30 Tage Urlaub.\n",
    reason: "Die neue Betriebsvereinbarung gilt seit Januar.",
  });

  const page = await anna.newPage();
  await page.goto(pageUrl(space, doc));
  await page.getByRole("link", { name: "1 offener Vorschlag zu dieser Seite" }).click();
  await expect(page.getByRole("link", { name: /Vorschläge.*1 offener Vorschlag/ })).toBeVisible();
  await proposalLink(page, "Urlaub").click();

  const changes = page.getByRole("region", { name: "Änderungen des Vorschlags" });
  await expect(changes.getByText("entfernt:", { exact: false }).first()).toBeAttached();
  await expect(changes.getByText(/30 Tage/)).toBeVisible();
  await expect(page.getByText("Die neue Betriebsvereinbarung gilt seit Januar.")).toBeVisible();
  await expect(page.getByText("Hilda").first()).toBeVisible();

  const accepted = page.waitForResponse(
    (r) => /\/api\/proposals\/[^/]+\/accept$/.test(new URL(r.url()).pathname) && r.ok(),
  );
  await page.getByRole("button", { name: "Annehmen" }).click();
  await accepted;
  await expect(page.getByRole("heading", { name: /Angenommen von/ })).toBeVisible();
  await page.getByRole("link", { name: /„Urlaub“ öffnen/ }).click();
  await expect(page.getByText("Es gibt 30 Tage Urlaub.")).toBeVisible();
  await expect(page.getByRole("link", { name: /offener Vorschlag zu dieser Seite/ })).toHaveCount(
    0,
  );
});

test("a proposal whose page changed meanwhile is merged in the conflict dialog", async () => {
  const before = "Ankunft um acht.\n\nPause um zwölf.\n\nSchluss um fünf.\n";
  const doc = await publishedPage(anna, space.id, "Arbeitszeit", before);
  seedProposal({
    email: OWNER.email,
    agentId: hilda.id,
    pageId: doc.id,
    content: "Ankunft um acht.\n\nPause um halb eins.\n\nSchluss um fünf.\n",
    reason: "So steht es im Aushang.",
  });
  // Someone edits the same paragraph before the proposal is decided.
  await call(anna, "PATCH", `/api/pages/${doc.id}`, {
    content_md: "Ankunft um acht.\n\nPause um eins.\n\nSchluss um fünf.\n",
    version: doc.version,
  });

  const page = await anna.newPage();
  await page.goto(`/spaces/${space.id}/proposals`);
  await proposalLink(page, "Arbeitszeit").click();
  await expect(page.getByText(/Die Seite hat sich seit dem Vorschlag geändert/)).toBeVisible();
  await page.getByRole("button", { name: "Annehmen" }).click();

  const dialog = page.getByRole("dialog", { name: "Die Seite hat sich geändert" });
  await expect(dialog.getByText(/1 Stelle wurde auf beiden Seiten geändert/)).toBeVisible();
  const conflict = dialog.getByRole("group", { name: "Konflikt 1" });
  await expect(conflict.getByText("Pause um eins.")).toBeVisible();
  await expect(conflict.getByText("Pause um halb eins.")).toBeVisible();
  const merged = dialog.getByRole("textbox", { name: "Zusammengeführter Text" });
  await expect(merged).toHaveValue(/Pause um eins\./);
  await conflict.getByRole("radio", { name: "Vorschlag übernehmen" }).check();
  await expect(merged).toHaveValue(/Pause um halb eins\./);
  await merged.fill(`${await merged.inputValue()}\nGilt ab März.\n`);

  const accepted = page.waitForResponse(
    (r) => /\/api\/proposals\/[^/]+\/accept$/.test(new URL(r.url()).pathname) && r.ok(),
  );
  await dialog.getByRole("button", { name: "Zusammengeführt annehmen" }).click();
  await accepted;
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Angenommen von/ })).toBeVisible();
  const now = await call(anna, "GET", `/api/pages/${doc.id}`);
  expect(now.content_md).toContain("Pause um halb eins.");
  expect(now.content_md).toContain("Gilt ab März.");
  expect(now.content_md).not.toContain("Pause um eins.");
});

test("the admin imports a SKILL.md and assigns the skill to an agent", async () => {
  const dir = mkdtempSync(join(tmpdir(), "herd-skill-"));
  const file = join(dir, "SKILL.md");
  writeFileSync(
    file,
    "---\nname: protokoll-schreiben\ndescription: Schreibt Protokolle im Format des Hauses.\n" +
      "license: MIT\n---\n# Protokoll\n\nErst die Beschlüsse, dann die Aufgaben.\n",
  );
  const page = await anna.newPage();
  await page.goto("/admin/skills");
  await page.getByRole("button", { name: "Importieren" }).click();
  const dialog = page.getByRole("dialog", { name: "Skills importieren" });
  await expect(dialog.getByText(/Nichts aus einem Skill wird ausgeführt/)).toBeVisible();
  await dialog.getByLabel("Datei (SKILL.md oder ZIP)").setInputFiles(file);
  await dialog.getByRole("button", { name: "Importieren" }).click();
  await expect(dialog.getByText("1 Skill angelegt")).toBeVisible();
  await expect(dialog.getByText(/Nicht übernommen: license/)).toBeVisible();
  await dialog.getByRole("button", { name: "Schließen" }).first().click();
  await expect(
    page.getByRole("list", { name: "Skills" }).getByRole("link", { name: "protokoll-schreiben" }),
  ).toBeVisible();

  await page.goto(`/admin/agents/${hilda.id}`);
  await page.getByRole("button", { name: "Skills zuweisen" }).click();
  const assign = page.getByRole("dialog", { name: "Skills zuweisen" });
  await assign.getByRole("checkbox", { name: /protokoll-schreiben/ }).check();
  const saved = page.waitForResponse(
    (r) => r.request().method() === "PUT" && r.url().endsWith(`/api/agents/${hilda.id}/skills`),
  );
  await assign.getByRole("button", { name: "Speichern" }).click();
  expect((await saved).ok()).toBeTruthy();
  await expect(
    page.getByRole("list", { name: "Skills des Agenten" }).getByText("protokoll-schreiben"),
  ).toBeVisible();
  const skills = await call(anna, "GET", `/api/agents/${hilda.id}/skills`);
  expect(skills.skills.map((s) => s.name)).toContain("protokoll-schreiben");
});

test("a person without AI sees no skills entry", async ({ browser }) => {
  const emil = await person(anna, EMIL);
  const assignments = await call(anna, "GET", "/api/ai/assignments/users?limit=100");
  if (!assignments.items.some((a) => a.user_id === emil.id)) {
    await call(anna, "PUT", `/api/ai/assignments/users/${emil.id}`, {
      no_ai: true,
      version: null,
    });
  }
  await call(anna, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "user",
    member_id: emil.id,
    role: "moderator",
  });
  const context = await browser.newContext();
  try {
    await signIn(context, EMIL);
    const me = await call(context, "GET", "/api/auth/me");
    expect(me.permissions).not.toContain("ai.use");
    const page = await context.newPage();
    await page.goto(`/spaces/${space.id}`);
    const tabs = page.getByRole("navigation", { name: "Ansichten des Bereichs" });
    await expect(tabs.getByRole("link", { name: /Wiki/ })).toBeVisible();
    await expect(tabs.getByRole("link", { name: "Skills" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Skills", exact: true })).toHaveCount(0);
    await page.goto(`/spaces/${space.id}/skills`);
    await expect(page.getByText("Skills sehen nur Personen mit KI.")).toBeVisible();
    const api = await context.request.get(`/api/skills?space_id=${space.id}`);
    expect(api.ok()).toBeFalsy();
  } finally {
    await context.close();
  }
});
