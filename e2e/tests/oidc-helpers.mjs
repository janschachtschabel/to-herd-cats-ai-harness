// Sign-in through OpenID Connect (plan M9 task 5): providers made through the admin
// API, all pointing at the OIDC stub that global-setup.mjs runs over https for
// `localhost` (public port + 7; `tests/support/oidc_stub.py`). The stub approves every
// authorization at once with the identity scripted last.
import { execFileSync } from "node:child_process";
import { expect, request as playwrightRequest } from "@playwright/test";
import { call } from "./helpers.mjs";

const port = Number(process.env.HERD_E2E_PORT || 18080);
export const OIDC_STUB = `https://localhost:${port + 7}`;
/** The client the stub knows (`OidcStubState`); its secret is in the app's environment. */
const CLIENT = { client_id: "herd-oidc-client", client_secret: { env: "HERD_OIDC_STUB_SECRET" } };

/** Resets the stub, then sets what the next sign-in brings: `identity` (claims such as
 *  `sub`, `email`, `hd`) and anything else of its state (`issuer_claim`, ...). */
export async function scriptOidc(script = {}) {
  const context = await playwrightRequest.newContext({ ignoreHTTPSErrors: true });
  try {
    for (const [path, data] of [
      ["/_stub/reset", {}],
      ["/_stub/script", script],
    ]) {
      const r = await context.post(`${OIDC_STUB}${path}`, { data });
      expect(r.ok(), `${path}: ${r.status()}`).toBeTruthy();
    }
  } finally {
    await context.dispose();
  }
}

async function providerKeyed(admin, key) {
  const list = await call(admin, "GET", "/api/admin/oidc-providers?limit=100");
  return list.items.find((p) => p.key === key) ?? null;
}

/** A generic provider at the stub (found again by key and brought to `fields`). */
export async function stubProvider(admin, key, name, fields = {}) {
  const found = await providerKeyed(admin, key);
  if (found) {
    return call(admin, "PATCH", `/api/admin/oidc-providers/${found.id}`, {
      version: found.version,
      enabled: true,
      ...fields,
    });
  }
  return call(admin, "POST", "/api/admin/oidc-providers", {
    kind: "generic",
    key,
    name,
    issuer: OIDC_STUB,
    ...CLIENT,
    enabled: true,
    ...fields,
  });
}

/** The Google preset, with its endpoints moved to the stub: the preset's issuer stays
 *  `https://accounts.google.com` (the stub signs with that `iss`), so only the stored
 *  discovery is changed, straight in the scratch database. Never the real Google. */
export async function stubGoogle(admin, fields = {}) {
  let google = await providerKeyed(admin, "google");
  if (google) {
    google = await call(admin, "PATCH", `/api/admin/oidc-providers/${google.id}`, {
      version: google.version,
      enabled: true,
      ...fields,
    });
  } else {
    google = await call(admin, "POST", "/api/admin/oidc-providers", {
      kind: "google",
      ...CLIENT,
      enabled: true,
      ...fields,
    });
  }
  const database = process.env.HERD_E2E_DATABASE_URL.replace("+asyncpg", "");
  const sql =
    `UPDATE oidc_provider SET authorization_endpoint = '${OIDC_STUB}/authorize', ` +
    `token_endpoint = '${OIDC_STUB}/token', jwks_uri = '${OIDC_STUB}/jwks', ` +
    `jwks = NULL, jwks_fetched_at = NULL WHERE id = '${google.id}'`;
  execFileSync("psql", [database, "-qc", sql], { stdio: "ignore" });
  return google;
}

/** Google's claims for a person of `domain` (a Workspace account: `hd` is its domain). */
export const googleIdentity = (sub, local, domain, name) => ({
  sub,
  email: `${local}@${domain}`,
  email_verified: true,
  hd: domain,
  name,
});

export const GOOGLE_ISSUER = "https://accounts.google.com";
