// Messaging around pages and oversight in real browsers (plan M3, task 12): a page's
// discussion shows the worker's system entries, a new one live after a page change;
// inspecting a direct message needs a reason, shows the messages read only, is audited,
// and the participants see that it happened.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";
import { CLARA, closePages, message, openLive, person, post, send } from "./messaging-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let space;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER);
  space = await teamSpace(anna, "Aufsicht"); // makes Ben, an editor here
  await signIn(ben, MEMBER);
});

test.afterEach(async () => closePages(anna, ben));

test.afterAll(async () => {
  await anna?.close();
  await ben?.close();
});

test("a page's discussion shows system entries, a new one live after a page change", async () => {
  const doc = await publishedPage(anna, space.id, "Regeln", "Erste Fassung.");
  const b = await openLive(ben, pageUrl(space, doc));
  await b.getByRole("button", { name: "Diskussion" }).click();
  const discussion = b.getByRole("complementary", { name: "Diskussion" });
  await expect(discussion.getByText("anna hat die Seite angelegt.")).toBeVisible();
  await expect(discussion.getByText("anna hat die Seite veröffentlicht.")).toBeVisible();

  await send(discussion, "Zur Seite schreiben", "Gilt das auch für Teilzeit?");
  await expect(message(discussion, "Ben", "Gilt das auch für Teilzeit?")).toBeVisible();

  // Anna changes the page and restores the first version: the entry arrives live.
  const changed = await call(anna, "PATCH", `/api/pages/${doc.id}`, {
    content_md: "Zweite Fassung.",
    version: doc.version,
  });
  await call(anna, "POST", `/api/pages/${doc.id}/versions/1/restore`, {
    version: changed.version,
  });
  await expect(discussion.getByText("anna hat Version 1 wiederhergestellt.")).toBeVisible();

  // Hiding system entries leaves the comment.
  await discussion.getByRole("checkbox", { name: "Systemmeldungen ausblenden" }).check();
  await expect(discussion.getByText("anna hat die Seite angelegt.")).toBeHidden();
  await expect(message(discussion, "Ben", "Gilt das auch für Teilzeit?")).toBeVisible();
});

test("inspecting a direct message needs a reason, is read only and audited", async ({
  browser,
}) => {
  const clara = await person(anna, CLARA);
  const dm = await call(ben, "POST", "/api/dms", { user_ids: [clara.id] });
  await post(ben, dm.id, "Vertraulich: die Gehaltsfrage.");

  // The API refuses a reason of blanks, as the form refuses a short one.
  const blank = await anna.request.post("/api/admin/dm-inspect", {
    data: { conversation_id: dm.id, reason: " ".repeat(12) },
    headers: { "X-Requested-With": "herd" },
  });
  expect(blank.status()).toBe(422);

  const a = await anna.newPage();
  await a.goto("/admin/dm-inspect");
  await a.getByRole("combobox", { name: "Person" }).fill("Ben");
  await a.getByRole("option", { name: "Ben" }).click();
  await a.getByRole("button", { name: "Einsicht beantragen" }).click();
  const reason = a.getByRole("textbox", { name: "Begründung" });
  await reason.fill("kurz");
  await a.getByRole("button", { name: "Einsicht beginnen" }).click();
  await expect(a.getByText("Mindestens 10 Zeichen.")).toBeVisible();
  await expect(a.getByRole("heading", { name: /^Einsicht:/ })).toHaveCount(0);

  await reason.fill("Beschwerde wegen Belästigung, Fall 42");
  await a.getByRole("button", { name: "Einsicht beginnen" }).click();
  await expect(a.getByRole("heading", { name: /^Einsicht:/ })).toBeVisible();
  await expect(a.getByText("Begründung: Beschwerde wegen Belästigung, Fall 42")).toBeVisible();
  const list = a.getByRole("list", { name: "Nachrichten, neueste zuerst" });
  await expect(list).toContainText("Vertraulich: die Gehaltsfrage.");
  // Read only: nothing to write, react, edit or delete.
  await expect(a.getByRole("textbox")).toHaveCount(0);
  for (const name of ["Reaktion hinzufügen", "Nachricht bearbeiten", "Nachricht löschen"]) {
    await expect(a.getByRole("button", { name })).toHaveCount(0);
  }

  const audit = await call(anna, "GET", "/api/admin/audit?action=dm.admin_access");
  const entry = audit.items.find((e) => e.target_id === dm.id);
  expect(entry?.details?.reason).toBe("Beschwerde wegen Belästigung, Fall 42");

  // The participants see it in the conversation (on the next load: not pushed live).
  const claraContext = await browser.newContext();
  try {
    await signIn(claraContext, CLARA);
    const c = await claraContext.newPage();
    await c.goto(`/c/${dm.id}`);
    await expect(c.getByRole("list", { name: "Einsichten der Verwaltung" })).toContainText(
      "Von der Verwaltung eingesehen am",
    );
    await expect(message(c, "Ben", "Vertraulich")).toBeVisible();
  } finally {
    await claraContext.close();
  }
});
