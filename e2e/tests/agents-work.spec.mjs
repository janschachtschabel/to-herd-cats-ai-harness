// Agents at work in real browsers (plan M6 task 13), with the OpenAI stub as the only
// provider: (a) a ticket assigned to a level-2 agent in the ticket view ends with the
// agent's comment and a status of category review, and no channel or DM got anything;
// (b) a release for a page change is approved and the call runs; a second one, whose
// page is edited before the release, is shown as stale and nothing runs; (c) the
// worker is killed in the middle of a run and started again: the run ends with exactly
// one answer and no step twice; (d) a mention in a channel is answered in the thread;
// (e) an agent's page proposal from a run is accepted by a moderator; (f) an agent
// updates its memory and the page shows under `_agenten`; (g) a person without AI sees
// none of it. The app runs in role all: its worker runs the agents.
import { expect, test } from "@playwright/test";
import { OWNER, call, pageUrl, publishedPage, signIn } from "./helpers.mjs";
import {
  channel,
  closePages,
  composer,
  message,
  openLive,
  person,
  send,
} from "./messaging-helpers.mjs";
import { aiBasics, scriptStub, stubLog } from "./ai-helpers.mjs";
import {
  chatRequests,
  finishedRun,
  grant,
  latestRun,
  levelAgent,
  member,
  messages,
  restartApp,
  runEvents,
} from "./agents-helpers.mjs";
import { conversationsSnapshot, discussion, status, ticket } from "./tickets-helpers.mjs";

test.describe.configure({ mode: "serial" });

const DM_COMPOSER = "Nachricht an Direktnachricht";
// A person of this file alone, with no AI (no_ai assignment), an editor in the space.
const FRITZ = { email: "fritz@e2e.example", password: "e2e-password-987", name: "Fritz" };
let anna;
let space;
let ole; // level 2: tickets, mentions, proposals, memory
let greta; // level 2, page proposals only after a release
let oleDm;
let werkbank; // the channel of the mention

const agentSays = (scope, name, text) =>
  scope.getByRole("article", { name: `Nachricht von ${name}` }).filter({ hasText: text });

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  const { connection } = await aiBasics(anna);
  ole = await levelAgent(anna, "Ole", connection, 2);
  greta = await levelAgent(anna, "Greta", connection, 2);
  await grant(anna, greta.id, "propose_page_change", "confirm");
  space = await call(anna, "POST", "/api/spaces", { name: "Werkstatt", kind: "team" });
  await member(anna, space.id, { type: "agent", id: ole.id }, "editor");
  await member(anna, space.id, { type: "agent", id: greta.id }, "editor");
  oleDm = await call(anna, "POST", "/api/dms", { agent_id: ole.id });
});

test.beforeEach(async () => scriptStub(anna.request));

test.afterEach(async () => closePages(anna));

test.afterAll(async () => anna?.close());

test("a ticket assigned to a level-2 agent ends in review with its comment, and nothing elsewhere", async () => {
  const made = await ticket(anna, space.id, "Bohrmaschine warten");
  const review = await status(anna, space.id, "Zur Prüfung");
  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          { name: "set_ticket_status", arguments: { key: made.key, status: review.name } },
        ],
      },
      { content: "Gewartet und geölt, bitte prüfen." },
    ],
  });
  const before = await conversationsSnapshot(anna);

  const page = await openLive(anna, `/tickets/${made.number}`);
  await page.getByRole("button", { name: "Jemandem zuweisen" }).click();
  await page.getByRole("combobox", { name: "Zugewiesen an" }).fill("Ole");
  await page.getByRole("option", { name: /Ole/ }).click();

  const comment = agentSays(discussion(page), "Ole", "Gewartet und geölt, bitte prüfen.");
  await expect(comment).toBeVisible({ timeout: 30_000 });
  await expect(comment.getByText("Von einer KI geschrieben")).toBeAttached();
  await expect(page.getByRole("combobox", { name: "Status" })).toHaveValue(review.id);
  const done = await call(anna, "GET", `/api/tickets/${made.number}`);
  expect(done.status.category).toBe("review");
  expect(done.assignee).toMatchObject({ type: "agent", id: ole.id });
  // Nothing about the ticket in any channel or direct message.
  expect(await conversationsSnapshot(anna)).toEqual(before);
});

test("a release runs the call; a release for a page edited meanwhile is stale and runs nothing", async () => {
  const one = await publishedPage(anna, space.id, "Werkzeugliste", "Hammer\nZange\n");
  const two = await publishedPage(anna, space.id, "Ordnung", "Links die Schrauben.\n");
  const dm = await call(anna, "POST", "/api/dms", { agent_id: greta.id });
  const proposals = async (pageId) => {
    const open = await call(anna, "GET", `/api/spaces/${space.id}/proposals?state=open&limit=100`);
    return open.items.filter((p) => p.page_id === pageId).length;
  };
  const card = (page) => page.getByRole("region", { name: "Freigabe" }).last();

  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          {
            name: "propose_page_change",
            arguments: {
              page_id: one.id,
              content_md: "Hammer\nZange\nSäge\n",
              reason: "Säge fehlt",
            },
          },
        ],
      },
      { content: "Die Säge ist vorgeschlagen." },
    ],
  });
  const page = await openLive(anna, `/c/${dm.id}`);
  await send(page, DM_COMPOSER, "Ergänze bitte die Säge in der Werkzeugliste.");
  const first = card(page);
  await expect(first.getByText("Wartet auf Entscheidung")).toBeVisible({ timeout: 30_000 });
  await expect(first.getByText("Du entscheidest.", { exact: false })).toBeVisible();
  expect(await proposals(one.id)).toBe(0); // nothing before the release
  await first.getByRole("button", { name: "Freigeben" }).click();
  await expect(first.getByText("Freigegeben und ausgeführt")).toBeVisible({ timeout: 30_000 });
  await expect(agentSays(page, "Greta", "Die Säge ist vorgeschlagen.")).toBeVisible();
  expect(await proposals(one.id)).toBe(1);

  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          {
            name: "propose_page_change",
            arguments: {
              page_id: two.id,
              content_md: "Links die Schrauben.\nRechts die Nägel.\n",
              reason: "Nägel fehlen",
            },
          },
        ],
      },
      { content: "Die Seite hatte sich geändert; ich frage neu, wenn nötig." },
    ],
  });
  await send(page, DM_COMPOSER, "Ergänze bitte die Nägel in der Ordnung.");
  const second = card(page);
  await expect(second.getByText("Wartet auf Entscheidung")).toBeVisible({ timeout: 30_000 });
  // Someone edits the page before the release.
  await call(anna, "PATCH", `/api/pages/${two.id}`, {
    content_md: "Links die Schrauben.\nOben die Dübel.\n",
    version: two.version,
  });
  await second.getByRole("button", { name: "Freigeben" }).click();
  await expect(second.getByText("Veraltet")).toBeVisible({ timeout: 30_000 });
  await expect(second.getByText(/Der Inhalt hat sich seit der Anfrage geändert/)).toBeVisible();
  await expect(agentSays(page, "Greta", "Die Seite hatte sich geändert")).toBeVisible();
  expect(await proposals(two.id)).toBe(0);
  // The API says so for the card (not the browser from the journal).
  const stale = await call(anna, "GET", "/api/approvals?state=approved&limit=100");
  const outcomes = stale.items.map((a) => a.outcome).sort();
  expect(outcomes).toEqual(["ran", "stale"]);
  expect(await stubLog(anna.request)).toContain("approval_stale");
});

test("a worker killed in the middle of a run is started again; the run ends once, no step twice", async () => {
  const title = "Neustart-Probe";
  // Step 1 makes a ticket. The provider call of step 2 takes 30 s with a reply nobody
  // will see: the worker dies meanwhile. The restarted worker replays step 1 from the
  // journal (no provider call, no second ticket) and asks once more for step 2.
  await scriptStub(anna.request, {
    replies: [
      { tool_calls: [{ name: "create_ticket", arguments: { space_id: space.id, title } }] },
      { content: "Diese Antwort geht mit dem Worker verloren.", delay: 30 },
      { content: "Das Ticket ist angelegt." },
    ],
  });
  const tickets = async () => {
    const found = await call(anna, "GET", `/api/tickets?space_id=${space.id}&q=${title}`);
    return found.items.filter((t) => t.title === title).length;
  };
  const before = await latestRun(anna, ole.id);
  const page = await openLive(anna, `/c/${oleDm.id}`);
  await send(page, DM_COMPOSER, "Lege bitte ein Ticket Neustart-Probe an.");
  // Step 1 is committed and step 2 waits on the provider: now the worker dies.
  await expect.poll(tickets, { timeout: 30_000 }).toBe(1);
  await expect
    .poll(async () => chatRequests(JSON.parse(await stubLog(anna.request))).length)
    .toBe(2);
  const running = await latestRun(anna, ole.id);
  expect(running.id).not.toBe(before?.id);
  expect(running.state).toBe("running");
  await restartApp(anna.request);

  const run = await finishedRun(anna, ole.id, before?.id);
  expect(run.id).toBe(running.id);
  expect(run.stop_reason).toBe("completed");
  expect(run.recoveries).toBeGreaterThanOrEqual(1);
  expect(await tickets()).toBe(1);
  const answers = (await messages(anna, oleDm.id)).filter((m) => m.run_id === run.id);
  expect(answers.map((m) => m.body_md)).toEqual(["Das Ticket ist angelegt."]);
  // The journal: one model answer per step and one tool call, nothing twice.
  const events = await runEvents(anna, run.id);
  const calls = events.filter((e) => e.kind === "tool_call");
  expect(calls.map((e) => e.content.name)).toEqual(["create_ticket"]);
  const steps = events.filter((e) => e.kind === "model_call").map((e) => e.content.step);
  expect(steps).toEqual([1, 2]);
  // The provider: step 1 once, step 2 twice (lost with the worker, then again).
  const chats = chatRequests(JSON.parse(await stubLog(anna.request)));
  expect(chats).toHaveLength(3);
  expect(JSON.stringify(chats[2].body)).toContain("create_ticket");

  // The page lost its live stream with the old process: loaded again, it shows the
  // one answer, and the lost reply nowhere.
  await page.reload();
  await expect(agentSays(page, "Ole", "Das Ticket ist angelegt.")).toBeVisible();
  await expect(page.getByText("Diese Antwort geht mit dem Worker verloren.")).toHaveCount(0);
});

test("a mention in a channel is answered in its thread", async () => {
  const room = await channel(anna, space.id, "werkbank");
  werkbank = room;
  await scriptStub(anna.request, { replies: [{ content: "Der Termin ist am Freitag." }] });
  const page = await openLive(anna, `/c/${room.id}`);
  const box = composer(page, "Nachricht an #werkbank");
  await box.pressSequentially("@Ol");
  await page
    .getByRole("listbox", { name: "Person erwähnen" })
    .getByRole("option", { name: /Ole/ })
    .click();
  await box.pressSequentially("wann ist der Wartungstermin?");
  await box.press("Enter");
  const asked = message(page, "anna", "wann ist der Wartungstermin?");
  await expect(asked).toBeVisible();

  const open = page.getByRole("button", { name: /Thread von anna öffnen, 1 Antwort/ });
  await expect(open).toBeVisible({ timeout: 30_000 });
  await open.click();
  const thread = page.getByRole("complementary", { name: "Thread" });
  const answer = agentSays(thread, "Ole", "Der Termin ist am Freitag.");
  await expect(answer).toBeVisible();
  await expect(answer.getByText("Von einer KI geschrieben")).toBeAttached();
  // In the channel itself only the question stands.
  const top = await messages(anna, room.id);
  expect(top.filter((m) => m.author.type === "agent")).toEqual([]);
});

test("an agent's page proposal from a run is accepted by a moderator", async () => {
  const doc = await publishedPage(anna, space.id, "Öffnungszeiten", "Montag bis Freitag.\n");
  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          {
            name: "propose_page_change",
            arguments: {
              page_id: doc.id,
              content_md: "Montag bis Freitag.\nSamstag nach Absprache.\n",
              reason: "Samstags wird auf Anfrage geöffnet.",
            },
          },
        ],
      },
      { content: "Ich habe einen Vorschlag gemacht." },
    ],
  });
  const before = await latestRun(anna, ole.id);
  await call(anna, "POST", `/api/conversations/${oleDm.id}/messages`, {
    body_md: "Ergänze bitte den Samstag.",
  });
  await finishedRun(anna, ole.id, before?.id);

  const page = await anna.newPage();
  await page.goto(pageUrl(space, doc));
  await page.getByRole("link", { name: "1 offener Vorschlag zu dieser Seite" }).click();
  await page
    .getByRole("list", { name: "Vorschläge" })
    .getByRole("link", { name: "Änderung an „Öffnungszeiten“" })
    .click();
  await expect(page.getByText("Samstags wird auf Anfrage geöffnet.")).toBeVisible();
  await expect(page.getByText("Von einer KI geschrieben").first()).toBeAttached();
  await expect(page.getByRole("link", { name: "Lauf ansehen" })).toBeVisible();
  await page.getByRole("button", { name: "Annehmen" }).click();
  await expect(page.getByRole("heading", { name: /Angenommen von/ })).toBeVisible();
  await page.getByRole("link", { name: /„Öffnungszeiten“ öffnen/ }).click();
  await expect(page.getByText("Samstag nach Absprache.")).toBeVisible();
  const now = await call(anna, "GET", `/api/pages/${doc.id}/versions?limit=1`);
  expect(now.items[0]).toMatchObject({ ai: true, source: "agent" });
});

test("an agent updates its memory and the page shows last in the tree under _agenten", async () => {
  await publishedPage(anna, space.id, "Zubehör", "Bohrer und Bits.\n");
  await scriptStub(anna.request, {
    replies: [
      {
        tool_calls: [
          {
            name: "update_memory",
            arguments: { space_id: space.id, content: "- Wartung immer freitags." },
          },
        ],
      },
      { content: "Gemerkt." },
    ],
  });
  const page = await openLive(anna, `/c/${oleDm.id}`);
  await send(page, DM_COMPOSER, "Merk dir bitte: Wartung immer freitags.");
  await expect(agentSays(page, "Ole", "Gemerkt.")).toBeVisible({ timeout: 30_000 });

  await page.goto(`/spaces/${space.id}`);
  const tree = page.getByRole("tree", { name: "Seiten" });
  const top = tree.locator(":scope > [role=treeitem]");
  const folder = tree.getByRole("treeitem", { name: /^Agenten/ });
  await expect(folder).toBeVisible();
  await expect(top.last()).toHaveAttribute(
    "data-page-id",
    await folder.getAttribute("data-page-id"),
  );
  await expect(folder.getByRole("img", { name: "Von Agenten geführt" }).first()).toBeVisible();
  await folder
    .getByRole("treeitem", { name: /Gedächtnis/ })
    .getByRole("link")
    .click();
  await expect(page).toHaveURL(/\/p\/_agenten\/ole\/gedaechtnis/);
  await expect(page.getByText(/Ein Agent führt diese Seite als sein Gedächtnis/)).toBeVisible();
  await expect(page.getByText("Wartung immer freitags.")).toBeVisible();
  await expect(page.getByRole("article").getByRole("link", { name: "Lauf ansehen" })).toBeVisible();
});

test("a person without AI sees none of it", async ({ browser }) => {
  const fritz = await person(anna, FRITZ);
  const assignments = await call(anna, "GET", "/api/ai/assignments/users?limit=100");
  if (!assignments.items.some((a) => a.user_id === fritz.id)) {
    await call(anna, "PUT", `/api/ai/assignments/users/${fritz.id}`, {
      no_ai: true,
      version: null,
    });
  }
  // A moderator here: he may assign tickets and mention anyone in the space.
  await member(anna, space.id, { type: "user", id: fritz.id }, "moderator");
  const worked = await call(anna, "GET", `/api/tickets?space_id=${space.id}&q=Bohrmaschine`);
  const number = worked.items[0].number;
  const run = await latestRun(anna, ole.id);
  const context = await browser.newContext();
  try {
    await signIn(context, FRITZ);
    const me = await call(context, "GET", "/api/auth/me");
    expect(me.permissions).not.toContain("ai.use");
    const page = await context.newPage();
    // The ticket the agent worked on: its comment belongs to the ticket, but no run
    // link, and no agent to assign.
    await page.goto(`/tickets/${number}`);
    await expect(agentSays(discussion(page), "Ole", "Gewartet und geölt")).toBeVisible();
    await expect(page.getByRole("link", { name: "Lauf ansehen" })).toHaveCount(0);
    await page.getByRole("button", { name: "Jemandem zuweisen" }).click();
    const directory = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/directory" && r.ok(),
    );
    await page.getByRole("combobox", { name: "Zugewiesen an" }).fill("Ole");
    const agentsIn = async (response) =>
      (await (await response).json()).items.filter((entry) => entry.type === "agent");
    expect(await agentsIn(directory)).toEqual([]);
    await expect(page.getByRole("option", { name: /Ole/ })).toHaveCount(0);
    // No agent to mention in the channel.
    const box = composer(page, "Nachricht an #werkbank");
    await page.goto(`/c/${werkbank.id}`);
    const mention = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/directory" && r.ok(),
    );
    await box.pressSequentially("@Ol");
    expect(await agentsIn(mention)).toEqual([]);
    await expect(page.getByRole("option", { name: /Ole/ })).toHaveCount(0);
    // No skills, no releases, no runs, no skill proposals.
    await page.goto(`/spaces/${space.id}`);
    const tabs = page.getByRole("navigation", { name: "Ansichten des Bereichs" });
    await expect(tabs.getByRole("link", { name: "Board" })).toBeVisible();
    await expect(tabs.getByRole("link", { name: "Skills" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^Freigaben/ })).toHaveCount(0);
    await page.goto(`/runs/${run.id}`);
    await expect(
      page.getByText("Diesen Lauf gibt es nicht, oder du darfst ihn nicht sehen."),
    ).toBeVisible();
    expect((await context.request.get(`/api/runs/${run.id}`)).status()).toBe(404);
    const approvals = await context.request.get("/api/approvals");
    if (approvals.ok()) expect((await approvals.json()).items).toEqual([]);
    else expect(approvals.status()).toBe(404);
    const skillProposals = await context.request.get("/api/skill-proposals");
    if (skillProposals.ok()) expect((await skillProposals.json()).items).toEqual([]);
    else expect(skillProposals.status()).toBe(404);
  } finally {
    await context.close();
  }
});
