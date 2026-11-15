// Setting up ticket scenarios through the API, and finding the board's columns and
// cards and a ticket's discussion in a page.
import { expect } from "@playwright/test";
import { call } from "./helpers.mjs";

/** A ticket in `spaceId` (in its first open status unless `status_id` says otherwise). */
export async function ticket(context, spaceId, title, extra = {}) {
  return call(context, "POST", `/api/spaces/${spaceId}/tickets`, { title, ...extra });
}

/** Changes a ticket against the version it has now (read first, as the UI does). */
export async function change(context, number, fields) {
  const current = await call(context, "GET", `/api/tickets/${number}`);
  return call(context, "PATCH", `/api/tickets/${number}`, {
    ...fields,
    version: current.version,
  });
}

/** The status of `spaceId` with this name (the defaults: Neu, In Arbeit, Zur Prüfung,
 * Erledigt, Verworfen). */
export async function status(context, spaceId, name) {
  const statuses = await call(context, "GET", `/api/spaces/${spaceId}/ticket-statuses?limit=100`);
  const found = statuses.items.find((s) => s.name === name);
  expect(found, `status ${name}`).toBeTruthy();
  return found;
}

/** A space of kind `open`: every person of the organisation reads it. */
export async function openSpace(context, name) {
  return call(context, "POST", "/api/spaces", { name, kind: "open" });
}

/** A column of the board, found by its status name (its heading also holds the count). */
export const column = (page, name) =>
  page
    .getByRole("group", { name: "Spalten des Boards" })
    .getByRole("region", { name: new RegExp(`^${name} `) });

/** A ticket's card on the board (in a page or a column). */
export const card = (scope, key) => scope.getByRole("article", { name: new RegExp(`^${key} `) });

/** A ticket's discussion: its comments and the grey timeline. */
export const discussion = (page) => page.getByRole("complementary", { name: "Kommentare" });

/** Every message id per channel and direct message `context` sees, with reply counts
 * and edit times: what must not change when only tickets change. */
export async function conversationsSnapshot(context) {
  const snapshot = {};
  for (const path of ["/api/channels", "/api/dms"]) {
    let cursor = null;
    do {
      const query = `limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`;
      const page = await call(context, "GET", `${path}?${query}`);
      for (const conversation of page.items) {
        const messages = await call(
          context,
          "GET",
          `/api/conversations/${conversation.id}/messages?limit=100`,
        );
        snapshot[conversation.id] = {
          kind: conversation.kind,
          more: messages.next_cursor !== null,
          messages: messages.items.map((m) => [m.id, m.reply_count, m.edited_at]),
        };
      }
      cursor = page.next_cursor;
    } while (cursor);
  }
  return snapshot;
}

/** A planned sprint of `spaceId` (two weeks from `starts_on`, default today). */
export async function sprint(
  context,
  spaceId,
  name,
  starts_on = new Date().toISOString().slice(0, 10),
) {
  const end = new Date(`${starts_on}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() + 13);
  return call(context, "POST", `/api/spaces/${spaceId}/sprints`, {
    name,
    starts_on,
    ends_on: end.toISOString().slice(0, 10),
  });
}

/** A sprint in the space's sprint list (its heading names it). */
export const sprintItem = (page, name) =>
  page.getByRole("article", { name: new RegExp(`^${name}`) });

/** A column of "Mein Board", found by its category (Offen, In Arbeit, Zur Prüfung, Erledigt). */
export const myColumn = (page, name) =>
  page
    .getByRole("group", { name: "Spalten von Mein Board" })
    .getByRole("region", { name: new RegExp(`^${name} `) });

/** A person's row of the daily view (`Nicht zugewiesen` for nobody's tickets). */
export const personRow = (page, name) =>
  page.getByRole("region", { name: new RegExp(`^${name}$`) });

/** A ticket's system entries in its thread, worded as the browser shows them. */
export const timelineEntry = (page, text) =>
  page.getByRole("complementary", { name: "Kommentare" }).getByText(text);
