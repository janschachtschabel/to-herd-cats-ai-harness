// The optional second factor (plan M9 task 16) in the real app: a person sets TOTP up
// in her profile (QR code, key, first code, recovery codes), then signs in with her
// password and a code, and with a recovery code that counts once; an admin resets the
// TOTP of someone who lost the device, who then signs in with the password alone.
import { expect, test } from "@playwright/test";
import { call, OWNER, signIn } from "./helpers.mjs";
import { Authenticator, enrollTotp, hotp } from "./totp-helpers.mjs";

// Their own addresses: no other spec signs in as them, so their TOTP stays theirs.
const TIA = { email: "tia@e2e.example", password: "e2e-password-tia-1", name: "Tia" };
const TOM = { email: "tom@e2e.example", password: "e2e-password-tom-1", name: "Tom" };
const KEY = /^(?:[A-Z2-7]{4} ){7}[A-Z2-7]{4}$/;

async function person(browser, who) {
  const admin = await browser.newContext();
  await signIn(admin, OWNER);
  const users = await call(admin, "GET", "/api/admin/users?limit=100");
  if (!users.items.some((u) => u.email === who.email)) {
    await call(admin, "POST", "/api/admin/users", who);
  }
  return admin;
}

/** The first step on the sign-in page; the second step's card is then on screen. */
async function passwordStep(page, who) {
  await page.goto("/login");
  await page.getByLabel("E-Mail-Adresse").fill(who.email);
  await page.getByLabel("Passwort").fill(who.password);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await expect(page.getByText("Zweiter Faktor", { exact: true })).toBeVisible();
}

/** A new browser through both steps with a recovery code; its page. */
async function withRecoveryCode(browser, who, recoveryCode) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await passwordStep(page, who);
  await page.getByRole("button", { name: "Wiederherstellungscode verwenden" }).click();
  await page.getByLabel("Wiederherstellungscode").fill(recoveryCode);
  await page.getByRole("button", { name: "Bestätigen" }).click();
  return page;
}

test("a person sets up TOTP in her profile, then signs in with a code or a recovery code", async ({
  browser,
}) => {
  const admin = await person(browser, TIA);
  const tia = await browser.newContext();
  await signIn(tia, TIA);
  const profile = await tia.newPage();
  await profile.goto("/profile");
  await expect(profile.getByText("Ausgeschaltet.")).toBeVisible();
  await profile.getByRole("button", { name: "Einrichten" }).click();
  const setup = profile.getByRole("dialog", { name: "Zwei-Faktor-Anmeldung einrichten" });
  await setup.getByLabel("Aktuelles Passwort").fill(TIA.password);
  await setup.getByRole("button", { name: "Weiter" }).click();
  await expect(setup.getByRole("img", { name: "QR-Code für die Authenticator-App" })).toBeVisible();
  const app = new Authenticator(await setup.getByText(KEY).textContent());
  await setup.getByLabel("Code aus der App").fill(await app.code());
  await setup.getByRole("button", { name: "Einschalten" }).click();
  await expect(setup.getByRole("status")).toHaveText(
    "Die Zwei-Faktor-Anmeldung ist eingeschaltet. Deine anderen Sitzungen wurden beendet.",
  );
  const recoveryCodes = await setup
    .getByRole("list", { name: "Deine Wiederherstellungscodes" })
    .getByRole("listitem")
    .allTextContents();
  expect(recoveryCodes).toHaveLength(10);
  await setup.getByRole("button", { name: "Gespeichert, schließen" }).click();
  await expect(profile.getByText("Noch 10 Wiederherstellungscodes übrig.")).toBeVisible();

  // The password alone opens no session: the API says a second factor is due.
  const halfway = await browser.newContext();
  const first = await halfway.request.post("/api/auth/login", {
    data: { email: TIA.email, password: TIA.password },
    headers: { "X-Requested-With": "herd" },
  });
  expect(first.status()).toBe(202);
  expect((await halfway.request.get("/api/auth/me")).status()).toBe(401);

  // A new browser: password, a wrong code, then the app's code.
  const laptop = await browser.newContext();
  const page = await laptop.newPage();
  await passwordStep(page, TIA);
  const code = page.getByLabel("Code aus der Authenticator-App");
  await code.fill(hotp(app.secret, 0)); // the code of 1970
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByText("Der Code stimmt nicht oder wurde schon verwendet.")).toBeVisible();
  await code.fill(await app.code());
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page).toHaveURL(/\/spaces/);
  expect((await call(laptop, "GET", "/api/auth/me")).user.email).toBe(TIA.email);

  // Without the device: a recovery code, once.
  const phone = await withRecoveryCode(browser, TIA, recoveryCodes[0]);
  await expect(phone).toHaveURL(/\/spaces/);
  const again = await withRecoveryCode(browser, TIA, recoveryCodes[0]);
  await expect(again.getByText("Der Code stimmt nicht oder wurde schon verwendet.")).toBeVisible();
  expect((await again.request.get("/api/auth/me")).status()).toBe(401);
  await Promise.all([phone.context().close(), again.context().close()]);
  await Promise.all([admin.close(), tia.close(), halfway.close(), laptop.close()]);
});

test("an admin resets the TOTP of someone who lost the device; the password then suffices", async ({
  browser,
}) => {
  const admin = await person(browser, TOM);
  const tom = await browser.newContext();
  await signIn(tom, TOM);
  await enrollTotp(tom, TOM.password);
  await tom.close();

  const page = await admin.newPage();
  await page.goto("/admin/users");
  const row = page.getByRole("row").filter({ hasText: TOM.email });
  await expect(row.getByLabel("Zwei-Faktor-Anmeldung eingeschaltet")).toBeVisible();
  await row.getByRole("button", { name: "Zwei-Faktor von Tom zurücksetzen" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Zwei-Faktor-Anmeldung von Tom zurücksetzen?",
  });
  await dialog.getByRole("button", { name: "Zurücksetzen" }).click();
  await expect(dialog).toBeHidden();
  await expect(row.getByLabel("Zwei-Faktor-Anmeldung eingeschaltet")).toBeHidden();

  const fresh = await browser.newContext();
  const signed = await fresh.newPage();
  await signed.goto("/login");
  await signed.getByLabel("E-Mail-Adresse").fill(TOM.email);
  await signed.getByLabel("Passwort").fill(TOM.password);
  await signed.getByRole("button", { name: "Anmelden" }).click();
  await expect(signed).toHaveURL(/\/spaces/);
  await Promise.all([admin.close(), fresh.close()]);
});
