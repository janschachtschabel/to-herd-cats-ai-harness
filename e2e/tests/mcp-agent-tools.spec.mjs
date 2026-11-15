// Internal agents calling external tools in real browsers (plan M8 task 12), with the
// OpenAI stub as the model and the MCP stub (https, localhost) as the external server:
// a level-4 agent reads with an external read tool and calls an external write tool,
// which waits for the asking person's release of its exact arguments; the run view
// shows one entry per call. Under the mark of a result read through the asker's own
// connector, a post where others read waits for her release, and the agent's answer
// in the shared channel stays held back. A worker lost while an external call is in
// flight leaves its outcome unknown, and the call is never sent again.
import { expect, test } from "@playwright/test";
import { OWNER, call, signIn } from "./helpers.mjs";
import { channel, closePages, composer, message, openLive, send } from "./messaging-helpers.mjs";
import { aiBasics, scriptStub } from "./ai-helpers.mjs";
import {
  finishedRun,
  latestRun,
  levelAgent,
  member,
  messages,
  restartApp,
  runEvents,
} from "./agents-helpers.mjs";
import {
  approveTool,
  externalToolName,
  mcpStubLog,
  scriptMcp,
  setGrants,
  stubServer,
  stubToolCalls,
} from "./mcp-helpers.mjs";

test.describe.configure({ mode: "serial" });

const DM_COMPOSER = "Nachricht an Direktnachricht";
const SERVER = "Werkbank-Tracker";
let anna;
let theo; // level 4: external write tools, always after a release
let theoDm;
let search; // the run-tool names of the server's tools
let create;

const agentSays = (scope, name, text) =>
  scope.getByRole("article", { name: `Nachricht von ${name}` }).filter({ hasText: text });

/** The run view's entries for one external tool ("Server · tool"). */
const callEntries = (page, server, tool) =>
  page
    .getByRole("list", { name: "Schritte des Laufs" })
    .getByRole("listitem")
    .filter({ hasText: `${server} · ${tool}` });

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  await signIn(anna, OWNER);
  const { connection } = await aiBasics(anna);
  theo = await levelAgent(anna, "Theo", connection, 4);
  const server = await stubServer(anna, SERVER);
  await approveTool(anna, server.id, "search_issues");
  await approveTool(anna, server.id, "create_issue");
  search = await externalToolName(anna, theo.id, SERVER, "search_issues");
  create = await externalToolName(anna, theo.id, SERVER, "create_issue");
  theoDm = await call(anna, "POST", "/api/dms", { agent_id: theo.id });
});

test.beforeEach(async () => {
  await setGrants(anna, theo.id, { [search]: "allow", [create]: "confirm" });
  await scriptStub(anna.request);
  await scriptMcp();
});

test.afterEach(async () => closePages(anna));

test.afterAll(async () => anna?.close());

test("an external write call runs only after the asker releases it; the run view shows one entry per call", async () => {
  await scriptMcp({
    results: {
      search_issues: { text: "Keine offenen Issues zur Lampe." },
      create_issue: { text: "Issue #7 angelegt." },
    },
  });
  await scriptStub(anna.request, {
    replies: [
      { tool_calls: [{ name: search, arguments: { q: "Lampe" } }] },
      { tool_calls: [{ name: create, arguments: { title: "Lampe in Halle 2 tauschen" } }] },
      { content: "Das Issue ist angelegt: #7." },
    ],
  });
  const before = await latestRun(anna, theo.id);
  const page = await openLive(anna, `/c/${theoDm.id}`);
  await send(page, DM_COMPOSER, "Lege bitte ein Issue für die Lampe in Halle 2 an.");

  const card = page.getByRole("region", { name: "Freigabe" }).last();
  await expect(card.getByText("Wartet auf Entscheidung")).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText(/Freigabe erbeten: externes Werkzeug create_issue/)).toBeVisible();
  await expect(card.getByText(`${SERVER} · create_issue`)).toBeVisible();
  const args = card.getByLabel("Argumente für den externen Server");
  await expect(args).toContainText("Lampe in Halle 2 tauschen");
  // Before the release only the read tool went out.
  expect((await stubToolCalls()).map((c) => c.name)).toEqual(["search_issues"]);

  await card.getByRole("button", { name: "Freigeben" }).click();
  await expect(card.getByText("Freigegeben und ausgeführt")).toBeVisible({ timeout: 30_000 });
  await expect(agentSays(page, "Theo", "Das Issue ist angelegt: #7.")).toBeVisible();
  const sent = await stubToolCalls();
  expect(sent).toEqual([
    { name: "search_issues", arguments: { q: "Lampe" } },
    { name: "create_issue", arguments: { title: "Lampe in Halle 2 tauschen" } },
  ]);

  // The journal holds two entries per external call (sending, then the answer); the
  // run view shows one per call, with the answer.
  const run = await finishedRun(anna, theo.id, before?.id);
  const external = (await runEvents(anna, run.id)).filter(
    (e) => e.kind === "tool_call" && e.content.source === "mcp",
  );
  expect(external).toHaveLength(4);
  await page.goto(`/runs/${run.id}`);
  for (const [tool, answer] of [
    ["search_issues", "Keine offenen Issues zur Lampe."],
    ["create_issue", "Issue #7 angelegt."],
  ]) {
    const entries = callEntries(page, SERVER, tool);
    await expect(entries).toHaveCount(1);
    await expect(entries.getByText("Externes Werkzeug")).toBeVisible();
    await entries.getByText("Ergebnis").click();
    await expect(entries.getByText(answer)).toBeVisible();
  }
});

test("under the mark of the asker's own connector a post where others read waits for her release, and the answer stays held back", async () => {
  // Module review M8 2, G2: no refusal any more; the release card shows exactly what
  // would be written, and the run's own answer in the shared channel stays held back.
  const server = await stubServer(anna, "Mein Tracker", { connector_scope: "personal" });
  await approveTool(anna, server.id, "search_issues");
  const own = await externalToolName(anna, theo.id, "Mein Tracker", "search_issues");
  await setGrants(anna, theo.id, { [own]: "allow" });
  await call(anna, "POST", "/api/ai/my-connectors", {
    name: "Mein Tracker",
    auth_kind: "bearer",
    mcp_server_id: server.id,
    secret: { value: "annas-eigenes-tracker-token" },
  });
  const hall = await call(anna, "POST", "/api/spaces", { name: "Werkhalle", kind: "team" });
  await member(anna, hall.id, { type: "agent", id: theo.id }, "editor");
  const room = await channel(anna, hall.id, "halle");
  const released = "Abnahme der Pumpe: Termin steht.";
  await scriptMcp({ results: { search_issues: { text: "Annas Termin: Freitag, 9 Uhr." } } });
  await scriptStub(anna.request, {
    replies: [
      { tool_calls: [{ name: own, arguments: { q: "Termin" } }] },
      {
        tool_calls: [
          { name: "post_message", arguments: { conversation_id: room.id, text: released } },
        ],
      },
      { content: "Laut Tracker: Freitag, 9 Uhr." },
    ],
  });

  const before = await latestRun(anna, theo.id);
  const page = await openLive(anna, `/c/${room.id}`);
  const box = composer(page, "Nachricht an #halle");
  await box.pressSequentially("@The");
  await page
    .getByRole("listbox", { name: "Person erwähnen" })
    .getByRole("option", { name: /Theo/ })
    .click();
  await box.pressSequentially("wann ist mein Termin?");
  await box.press("Enter");
  await expect(message(page, "anna", "wann ist mein Termin?")).toBeVisible();

  // The post waits for Anna's release: the card says why and shows the text, open.
  await expect
    .poll(async () => (await call(anna, "GET", "/api/approvals?state=pending")).items.length, {
      timeout: 30_000,
    })
    .toBe(1);
  await page.goto("/approvals");
  const card = page.getByRole("region", { name: "Freigabe" }).last();
  await expect(card.getByText(/^Persönlich:/)).toBeVisible();
  await expect(card.getByText(released)).toBeVisible();
  expect(JSON.stringify(await messages(anna, room.id))).not.toContain(released);
  await card.getByRole("button", { name: "Freigeben" }).click();

  const run = await finishedRun(anna, theo.id, before?.id);
  expect(run.stop_reason).toBe("policy_blocked"); // its answer stays held back
  // The call went out with Anna's own credential; only the released text was posted.
  const log = await mcpStubLog();
  const called = log.find((r) => r.body.includes('"tools/call"'));
  expect(called.headers.authorization).toBe("Bearer annas-eigenes-tracker-token");
  const top = await messages(anna, room.id);
  const posted = top.filter((m) => m.body_md === released);
  expect(posted).toHaveLength(1);
  expect(posted[0].personal).toBe(false); // she decided to publish it
  expect(JSON.stringify(top)).not.toContain("Freitag");
  for (const asked of top.filter((m) => m.reply_count > 0)) {
    const replies = await call(anna, "GET", `/api/messages/${asked.id}/replies?limit=100`);
    expect(JSON.stringify(replies.items)).not.toContain("Freitag");
  }
  await page.goto(`/runs/${run.id}`);
  await expect(page.getByText(/persönlichen Zugang der fragenden Person/)).toBeVisible();
});

test("a worker lost during an external call leaves its outcome unknown, and the call is not sent again", async () => {
  // The read call's answer takes 30 s: the worker dies meanwhile. The new worker takes
  // the run up from its journal and never sends the call again.
  await scriptMcp({ results: { search_issues: { text: "Zu spät.", delay: 30 } } });
  await scriptStub(anna.request, {
    replies: [
      { tool_calls: [{ name: search, arguments: { q: "Pumpe" } }] },
      { content: "Ich konnte im Tracker nichts sicher nachsehen." },
    ],
  });
  const before = await latestRun(anna, theo.id);
  await call(anna, "POST", `/api/conversations/${theoDm.id}/messages`, {
    body_md: "Gibt es ein Issue zur Pumpe?",
  });
  await expect.poll(async () => (await stubToolCalls()).length, { timeout: 30_000 }).toBe(1);
  await restartApp(anna.request);

  const run = await finishedRun(anna, theo.id, before?.id);
  expect(run.stop_reason).toBe("completed");
  expect(run.recoveries).toBeGreaterThanOrEqual(1);
  expect(await stubToolCalls()).toEqual([{ name: "search_issues", arguments: { q: "Pumpe" } }]);
  const answers = (await messages(anna, theoDm.id)).filter((m) => m.run_id === run.id);
  expect(answers.map((m) => m.body_md)).toEqual(["Ich konnte im Tracker nichts sicher nachsehen."]);

  const page = await anna.newPage();
  await page.goto(`/runs/${run.id}`);
  const entries = callEntries(page, SERVER, "search_issues");
  await expect(entries).toHaveCount(1);
  await expect(entries.getByText(/Ausgang unbekannt/)).toBeVisible();
  await expect(page.getByText("Zu spät.")).toHaveCount(0);
});
