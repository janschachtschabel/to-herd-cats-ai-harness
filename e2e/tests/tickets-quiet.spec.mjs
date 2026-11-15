// Acceptance of M4 (spec 14/M4): "Kanäle bleiben frei von Ticketmeldungen". After ten
// ticket changes, processed by the worker (their timeline entries are in the ticket's
// thread), no channel and no direct message holds a new message: checked through the
// API for everything Anna and Ben see, and in Ben's browser. The same holds for a
// ticket an agent works on (M6 task 8): its run comments in the ticket's thread only.
import { expect, test } from "@playwright/test";
import { aiBasics, scriptStub } from "./ai-helpers.mjs";
import { MEMBER, OWNER, call, publishedPage, signIn, teamSpace } from "./helpers.mjs";
import { channel, closePages, message, openLive, post } from "./messaging-helpers.mjs";
import { change, conversationsSnapshot, status, ticket } from "./tickets-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  ben = await browser.newContext();
  await signIn(anna, OWNER);
});

test.afterEach(async () => closePages(anna, ben));

test.afterAll(async () => {
  await anna?.close();
  await ben?.close();
});

/** The system entries of a ticket's thread, by key (the worker writes them). */
async function timeline(context, number) {
  const thread = await call(context, "GET", `/api/tickets/${number}/thread`);
  const page = await call(context, "GET", `/api/conversations/${thread.id}/messages?limit=100`);
  return page.items.filter((m) => m.kind === "system").map((m) => m.system.key);
}

test("ten ticket changes leave every channel and direct message as it was", async () => {
  const space = await teamSpace(anna, "Ruhe"); // makes Ben, an editor here
  const benUser = await signIn(ben, MEMBER);
  const room = await channel(anna, space.id, "allgemein");
  await post(anna, room.id, "Guten Morgen zusammen.");
  const dm = await call(anna, "POST", "/api/dms", { user_ids: [benUser.id] });
  await post(anna, dm.id, "Kurze Frage zum Plan.");
  const doc = await publishedPage(anna, space.id, "Ablauf", "Erst planen, dann tun.");

  const before = {
    anna: await conversationsSnapshot(anna),
    ben: await conversationsSnapshot(ben),
  };
  expect(before.ben[room.id].messages).toHaveLength(1);
  expect(before.ben[dm.id].messages).toHaveLength(1);
  // Unread counts of the others (the channel Ben is about to open he reads, so not it).
  const unread = async () => {
    const page = await call(ben, "GET", "/api/conversations/unread?limit=100");
    return page.items.filter(
      (u) => u.conversation_id in before.ben && u.conversation_id !== room.id,
    );
  };
  const unreadBefore = await unread();
  expect(unreadBefore.find((u) => u.conversation_id === dm.id)?.unread).toBe(1);
  const b = await openLive(ben, `/c/${room.id}`);
  await expect(message(b, "anna", "Guten Morgen zusammen.")).toBeVisible();

  // Ten changes: two tickets, then one field after another, a page link and a comment.
  const epic = await ticket(anna, space.id, "Umzug", { kind: "epic" }); // 1
  const made = await ticket(anna, space.id, "Kisten packen"); // 2
  const key = made.key;
  await change(anna, made.number, { assignee: { type: "user", id: benUser.id } }); // 3
  const active = await status(anna, space.id, "In Arbeit");
  await change(anna, made.number, { status_id: active.id }); // 4
  await change(anna, made.number, { priority: "urgent" }); // 5
  await change(anna, made.number, { due_on: "2026-12-01" }); // 6
  await change(anna, made.number, { title: `Kisten packen (${key})` }); // 7
  await change(anna, made.number, { description_md: `Siehe #allgemein und ${key}.` }); // 8
  await change(anna, made.number, { parent_id: epic.id }); // 9
  await call(anna, "PUT", `/api/tickets/${made.number}/pages/${doc.id}`); // 10
  const thread = await call(ben, "GET", `/api/tickets/${made.number}/thread`);
  await post(ben, thread.id, "Ich fange morgen an.");

  // The worker has handled every change: one entry each in the ticket's thread.
  await expect
    .poll(() => timeline(anna, made.number), { timeout: 30_000 })
    .toEqual([
      "ticket.page_linked",
      "ticket.parent_changed",
      "ticket.description_changed",
      "ticket.title_changed",
      "ticket.due_changed",
      "ticket.priority_changed",
      "ticket.status_changed",
      "ticket.assigned",
      "ticket.created",
    ]);
  await expect.poll(() => timeline(anna, epic.number)).toEqual(["ticket.created"]);

  // Through the API: every channel and direct message is as it was, for both of them.
  expect(await conversationsSnapshot(anna)).toEqual(before.anna);
  expect(await conversationsSnapshot(ben)).toEqual(before.ben);
  expect(await unread()).toEqual(unreadBefore);

  // In Ben's browser: the channel (open all along, and loaded anew) and the direct
  // message hold their one message each; the ticket's thread holds the timeline.
  const articles = b.getByRole("article", { name: /^Nachricht von / });
  await expect(articles).toHaveCount(1);
  await b.reload();
  await expect(message(b, "anna", "Guten Morgen zusammen.")).toBeVisible();
  await expect(articles).toHaveCount(1);
  await b.goto(`/c/${dm.id}`);
  await expect(message(b, "anna", "Kurze Frage zum Plan.")).toBeVisible();
  await expect(articles).toHaveCount(1);
  await b.goto(`/tickets/${made.number}`);
  await expect(b.getByText("anna hat das Ticket Ben zugewiesen.")).toBeVisible();
  await expect(message(b, "Ben", "Ich fange morgen an.")).toBeVisible();
});

test("a ticket an agent works on leaves every channel and direct message as it was", async () => {
  const { hilda } = await aiBasics(anna);
  const space = await teamSpace(anna, "Ruhe mit Hilda");
  await call(anna, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "agent",
    member_id: hilda.id,
    role: "editor",
  });
  const room = await channel(anna, space.id, "werkstatt");
  await post(anna, room.id, "Wer räumt heute auf?");
  await call(anna, "POST", "/api/dms", { agent_id: hilda.id });
  const before = await conversationsSnapshot(anna);
  const made = await ticket(anna, space.id, "Lager zählen");
  const review = await status(anna, space.id, "Zur Prüfung");
  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          { name: "set_ticket_status", arguments: { key: made.key, status: review.name } },
        ],
      },
      { content: "Gezählt, bitte prüfen." },
    ],
  });

  await change(anna, made.number, { assignee: { type: "agent", id: hilda.id } });
  const comments = async () => {
    const thread = await call(anna, "GET", `/api/tickets/${made.number}/thread`);
    const page = await call(anna, "GET", `/api/conversations/${thread.id}/messages?limit=100`);
    return page.items.filter((m) => m.kind === "agent").map((m) => m.body_md);
  };
  await expect.poll(comments, { timeout: 30_000 }).toEqual(["Gezählt, bitte prüfen."]);
  const done = await call(anna, "GET", `/api/tickets/${made.number}`);
  expect(done.status.category).toBe("review");
  await expect
    .poll(() => timeline(anna, made.number), { timeout: 30_000 })
    .toContain("ticket.status_changed");
  expect(await conversationsSnapshot(anna)).toEqual(before);
});
