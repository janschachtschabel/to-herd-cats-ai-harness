// Sign-in through OpenID Connect (plan M9 task 5) in the real app against the OIDC
// stub: a person links an account in the profile and then signs in with it; someone
// from an allowed domain registers through the Google preset and starts as a member
// without AI; someone from another domain is refused with the reason on the page.
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

const DORA = { email: "dora@e2e.example", password: "e2e-password-789", name: "Dora" };

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
  if (!(await userNamed(admin, DORA.email))) {
    await call(admin, "POST", "/api/admin/users", DORA);
  }

  const dora = await newContext(browser);
  await signIn(dora, DORA);
  // The address at the provider need not match: linking from the profile is explicit.
  await scriptOidc({ identity: { sub: "dora-at-firma", email: "d.privat@elsewhere.example" } });
  const profile = await dora.newPage();
  await profile.goto("/profile");
  await profile.getByRole("button", { name: "Mit Firmen-Login verknüpfen" }).click();
  await expect(profile).toHaveURL(/\/profile\?linked=firma$/);
  await expect(profile.getByText("Das Konto bei Firmen-Login ist jetzt verknüpft.")).toBeVisible();
  await expect(
    profile.getByRole("button", { name: "Verknüpfung mit Firmen-Login lösen" }),
  ).toBeVisible();

  // A browser without a session: the button on the sign-in page brings Dora in.
  const fresh = await newContext(browser);
  const page = await fresh.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "Anmelden mit Firmen-Login" }).click();
  await expect(page).toHaveURL(/\/spaces/);
  const me = await call(fresh, "GET", "/api/auth/me");
  expect(me.user.email).toBe(DORA.email);
  await Promise.all([admin.close(), dora.close(), fresh.close()]);
});

test("someone from an allowed domain registers through Google and starts without AI", async ({
  browser,
}) => {
  const admin = await adminContext(browser);
  // AI for everyone by default: the new account is the exception (its own "no AI").
  await standardAssignment(admin, await stubConnection(admin, "Stub"));
  await stubGoogle(admin, { allow_signup: true, allowed_domains: ["firma.example"] });
  await scriptOidc({
    identity: googleIdentity("g-clara", "clara", "firma.example", "Clara Neu"),
    issuer_claim: GOOGLE_ISSUER,
  });

  const clara = await newContext(browser);
  const page = await clara.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "Mit Google anmelden" }).click();
  await expect(page).toHaveURL(/\/spaces/);
  const me = await call(clara, "GET", "/api/auth/me");
  expect(me.user).toMatchObject({ email: "clara@firma.example", name: "Clara Neu" });
  expect(me.user.system_role).toBe("member");
  expect(me.permissions).not.toContain("ai.use");
  expect(me.ai_model).toBeNull();
  // Her own space is there; the agents' section is not.
  await expect(page.getByRole("heading", { name: "Bereiche", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agenten" })).toHaveCount(0);
  await Promise.all([admin.close(), clara.close()]);
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
