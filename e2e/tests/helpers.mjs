// Setting up through the API, and signing a browser context in, as the SPA does.
import { expect } from "@playwright/test";
import { OWNER } from "../global-setup.mjs";

export { OWNER };
export const MEMBER = { email: "ben@e2e.example", password: "e2e-password-456", name: "Ben" };
const HEADERS = { "X-Requested-With": "herd" };

/** Signs the context in: its requests and its pages share the session cookie. */
export async function signIn(context, { email, password }) {
  const r = await context.request.post("/api/auth/login", {
    data: { email, password },
    headers: HEADERS,
  });
  expect(r.status(), await r.text()).toBe(200);
  return (await r.json()).user;
}

export async function call(context, method, path, data) {
  const r = await context.request.fetch(path, { method, data, headers: HEADERS });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? null : r.json();
}

/** A team space with Ben as an editor; created once per run. */
export async function teamSpace(context, name) {
  const space = await call(context, "POST", "/api/spaces", { name, kind: "team" });
  const users = await call(context, "GET", "/api/admin/users?limit=100");
  let ben = users.items.find((u) => u.email === MEMBER.email);
  ben ??= await call(context, "POST", "/api/admin/users", MEMBER);
  await call(context, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "user",
    member_id: ben.id,
    role: "editor",
  });
  return space;
}

export async function publishedPage(context, spaceId, title, content_md) {
  const page = await call(context, "POST", `/api/spaces/${spaceId}/pages`, { title, content_md });
  return call(context, "POST", `/api/pages/${page.id}/publish`, { version: page.version });
}

export const pageUrl = (space, page, view) =>
  `/spaces/${space.id}/p/${page.path}${view ? `?view=${view}` : ""}`;
