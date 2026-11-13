// Setting up messaging scenarios: a third person, channels and direct messages through
// the API, and pages that wait until their live stream is open.
import { expect } from "@playwright/test";
import { MEMBER, call } from "./helpers.mjs";

export const CLARA = { email: "clara@e2e.example", password: "e2e-password-789", name: "Clara" };

/** A person made by the admin context, once per run (found again on later calls). */
export async function person(admin, { email, password, name }) {
  const users = await call(admin, "GET", "/api/admin/users?limit=100");
  return (
    users.items.find((u) => u.email === email) ??
    (await call(admin, "POST", "/api/admin/users", { email, password, name }))
  );
}

export const ben = (admin) => person(admin, MEMBER);

export async function channel(context, spaceId, name) {
  return call(context, "POST", `/api/spaces/${spaceId}/channels`, { name });
}

export async function post(context, conversationId, body_md, extra = {}) {
  return call(context, "POST", `/api/conversations/${conversationId}/messages`, {
    body_md,
    ...extra,
  });
}

/**
 * Opens `path` in a new page of `context` and returns once the page's live stream
 * (`/api/stream`) answered: from then on every event reaches it, so a message sent
 * afterwards must arrive live (without the stream it would only come with a reload).
 */
export async function openLive(context, path) {
  const page = await context.newPage();
  const stream = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/stream" && r.status() === 200,
  );
  await page.goto(path);
  await stream;
  return page;
}

/** The composer: a combobox (its popup is the mention list). */
export const composer = (page, name) => page.getByRole("combobox", { name });

/** Types a message into the composer and sends it with Enter. */
export async function send(page, name, text) {
  const box = composer(page, name);
  await box.fill(text);
  await box.press("Enter");
  await expect(box).toHaveValue("");
}

export const message = (page, author, text) =>
  page.getByRole("article", { name: `Nachricht von ${author}` }).filter({ hasText: text });

export async function closePages(...contexts) {
  for (const context of contexts) {
    for (const page of context?.pages() ?? []) await page.close();
  }
}
