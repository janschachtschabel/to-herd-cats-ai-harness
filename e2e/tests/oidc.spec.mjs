// Sign-in through OpenID Connect (plan M9 task 5) in the real app against the OIDC
// stub: a person links an account in the profile and then signs in with it; someone
// from an allowed domain registers through the Google preset, waits for an admin's
// approval (plan M9 task 5b) and then starts as a member without AI; someone from
// another domain is refused with the reason on the page.
import { expect, test } from "@playwright/test";
import { stubConnection, standardAssignment } from "./ai-helpers.mjs";
import { call, OWNER, signIn } from "./helpers.mjs";
import {
  GOOGLE_ISSUER,
  googleIdentity,
  scriptOidc,
  stubGoogle,
  stubProvider,
} from "./oidc-helpers.mjs";

// Her own address: ai-agents.spec.mjs creates dora@e2e.example with another password.
const OLGA = { email: "olga@e2e.example", password: "e2e-password-789", name: "Olga" };

/** A browser context that accepts the stub's certificate (the run's own). */
const newContext = (browser) => browser.newContext({ ignoreHTTPSErrors: true });

async function adminContext(browser) {
  const admin = await newContext(browser);
  await signIn(admin, OWNER);
  return admin;
}

async function userNamed(admin, email) {
  const users = await call(admin, "GET", "/api/admin/users?limit=100");
  return users.items.find((u) => u.email === email) ?? null;
}

test("a person links an account in the profile and then signs in with it", async ({
  browser,
}) => {
  const admin = await adminContext(browser);
  await stubProvider(admin, "firma", "Firmen-Login");
  if (!(await userNamed(admin, OLGA.email))) {
    await call(admin, "POST", "/api/admin/users", OLGA);
  }

  const olga = await newContext(browser);
  await signIn(olga, OLGA);
  // The address at the provider need not match: linking from the profile is explicit.
  await scriptOidc({ identity: { sub: "olga-at-firma", email: "o.privat@elsewhere.example" } });
  const profile = await olga.newPage();
  await profile.goto("/profile");
  await profile.getByRole("button", { name: "Mit Firmen-Login verknüpfen" }).click();
  // A new way into the account: she proves herself again with her password (J9).
  const reauth = profile.getByRole("dialog", { name: "Erneut anmelden" });
  await reauth.getByLabel("Aktuelles Passwort").fill(OLGA.password);
  await reauth.getByRole("button", { name: "Weiter zum Anbieter" }).click();
  await expect(profile).toHaveURL(/\/profile\?linked=firma$/);
  await expect(profile.getByText("Das Konto bei Firmen-Login ist jetzt verknüpft.")).toBeVisible();
  await expect(
    profile.getByRole("button", { name: "Verknüpfung mit Firmen-Login lösen" }),
  ).toBeVisible();

  // A browser without a session: the button on the sign-in page brings Olga in.
  const fresh = await newContext(browser);
  const page = await fresh.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "Anmelden mit Firmen-Login" }).click();
  await expect(page).toHaveURL(/\/spaces/);
  const me = await call(fresh, "GET", "/api/auth/me");
  expect(me.user.email).toBe(OLGA.email);
  await Promise.all([admin.close(), olga.close(), fresh.close()]);
});

test("someone from an allowed domain registers through Google, waits for approval and starts without AI", async ({
  browser,
}) => {
  const admin = await adminContext(browser);
  // AI for everyone by default: the new account is the exception (its own "no AI").
  await standardAssignment(admin, await stubConnection(admin, "Stub"));
  await stubGoogle(admin, { allow_signup: true, allowed_domains: ["firma.example"] });
  const clara = googleIdentity("g-clara", "clara", "firma.example", "Clara Neu");
  await scriptOidc({ identity: clara, issuer_claim: GOOGLE_ISSUER });

  const claraContext = await newContext(browser);
  const page = await claraContext.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "Mit Google anmelden" }).click();
  // The account exists but nobody gets in without an admin's approval.
  await expect(page).toHaveURL(/\/login\?error=oidc\.account_pending$/);
  await expect(page.getByRole("heading", { name: "Dein Konto wartet auf Freigabe" })).toBeVisible();
  await expect(page.getByLabel("Passwort")).toHaveCount(0);
  expect((await claraContext.request.get("/api/auth/me")).status()).toBe(401);

  // The admin sees the count, the waiting account and approves it.
  const adminPage = await admin.newPage();
  await adminPage.goto("/admin/users");
  const nav = adminPage.getByRole("link", { name: /Personen/ });
  await expect(nav.getByText("1 Konto wartet auf Freigabe")).toBeAttached();
  await adminPage.getByRole("link", { name: /Wartet auf Freigabe/ }).click();
  await expect(adminPage).toHaveURL(/filter=pending/);
  await adminPage.getByRole("button", { name: "Clara Neu freigeben" }).click();
  const dialog = adminPage.getByRole("dialog");
  await dialog.getByRole("button", { name: "Freigeben" }).click();
  await expect(dialog).toBeHidden();
  await expect(adminPage.getByText("Niemand wartet auf Freigabe.")).toBeVisible();

  // Now the same sign-in brings her in.
  await scriptOidc({ identity: clara, issuer_claim: GOOGLE_ISSUER });
  await page.getByRole("link", { name: "Zur Anmeldung" }).click();
  await page.getByRole("link", { name: "Mit Google anmelden" }).click();
  await expect(page).toHaveURL(/\/spaces/);
  const me = await call(claraContext, "GET", "/api/auth/me");
  expect(me.user).toMatchObject({ email: "clara@firma.example", name: "Clara Neu" });
  expect(me.user.system_role).toBe("member");
  expect(me.permissions).not.toContain("ai.use");
  expect(me.ai_model).toBeNull();
  // Her own space is there; the agents' section is not.
  await expect(page.getByRole("heading", { name: "Bereiche", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agenten" })).toHaveCount(0);
  await Promise.all([admin.close(), claraContext.close()]);
});

test("someone from another domain is refused, with the reason on the sign-in page", async ({
  browser,
}) => {
  const admin = await adminContext(browser);
  await stubGoogle(admin, { allow_signup: true, allowed_domains: ["firma.example"] });
  await scriptOidc({
    identity: googleIdentity("g-max", "max", "andere.example", "Max Fremd"),
    issuer_claim: GOOGLE_ISSUER,
  });

  const max = await newContext(browser);
  const page = await max.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "Mit Google anmelden" }).click();
  await expect(page).toHaveURL(/\/login\?error=oidc\.domain_not_allowed$/);
  await expect(
    page.getByText("Konten dieser Domain können sich hier nicht selbst registrieren."),
  ).toBeVisible();
  await expect(page.getByLabel("E-Mail-Adresse")).toBeVisible();
  expect(await userNamed(admin, "max@andere.example")).toBeNull();
  await Promise.all([admin.close(), max.close()]);
});
