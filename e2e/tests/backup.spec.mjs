// Verwaltung → Sicherung (plan M9 Task 13) in the real app: the owner asks for a backup,
// the worker makes it and the list follows live; an archive changed on disk afterwards
// fails the check, which blocks restoring; an unchanged copy uploads and is listed.
// Nothing is restored here: the files share one database.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { call, OWNER, signIn } from "./helpers.mjs";
import { openLive } from "./messaging-helpers.mjs";

const BACKUP_DIR = process.env.HERD_E2E_BACKUP_DIR;

test("the owner makes a backup, and a manipulated archive fails the check", async ({ context }) => {
  test.setTimeout(180_000);
  await signIn(context, OWNER);
  // Listening before asking: the worker's note (backup.changed) must reach the page.
  const page = await openLive(context, "/admin/backup");
  await expect(page.getByRole("heading", { name: "Sicherung", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sicherung" })).toBeVisible();

  await page.getByRole("button", { name: "Jetzt sichern" }).click();
  const runs = page.getByRole("region", { name: "Sicherungen" });
  const made = runs.getByRole("row").filter({ hasText: "Verwaltung" }).first();
  await expect(made).toContainText("gelungen", { timeout: 120_000 });

  const { items } = await call(context, "GET", "/api/backups");
  const run = items.find((r) => r.trigger === "admin" && r.state === "ok");
  expect(run?.archive).toBeTruthy();
  const name = run.archive;
  const archives = page.getByRole("region", { name: "Archive" });
  await expect(archives.getByRole("cell", { name, exact: true })).toBeVisible();

  // One byte changed after the backup: the sidecar's checksum no longer fits.
  const path = join(BACKUP_DIR, name);
  const original = readFileSync(path);
  const changed = Buffer.from(original);
  const at = Math.floor(changed.length / 2);
  changed[at] = changed[at] ^ 0xff;
  writeFileSync(path, changed);

  await page.getByRole("button", { name: `${name} prüfen` }).click();
  const check = page.getByRole("region", { name: `Prüfung von ${name}` });
  await expect(
    check.getByText("Das Archiv wurde nach dem Sichern verändert (Prüfsumme stimmt nicht)."),
  ).toBeVisible({ timeout: 60_000 });
  await expect(check.getByText("Einspielen ist gesperrt", { exact: false })).toBeVisible();
  await expect(check.getByRole("button", { name: "Einspielen …" })).toBeDisabled();

  // The unchanged bytes, uploaded: checked, kept under a name of their own, listed.
  await page.getByLabel("Archiv (.tar)").setInputFiles({
    name: "von-woanders.tar",
    mimeType: "application/x-tar",
    buffer: original,
  });
  const uploaded = page.getByRole("status").filter({ hasText: "ist hochgeladen und geprüft" });
  await expect(uploaded).toBeVisible({ timeout: 60_000 });
  await expect(archives.getByRole("row").filter({ hasText: "hochgeladen" })).toHaveCount(1);
});
