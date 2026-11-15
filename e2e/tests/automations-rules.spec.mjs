// Event rules and the page review in real browsers (plan M7 task 10), with the OpenAI
// stub and the app's settable clock (only in this harness): (a) publishing a page
// starts a run in the space's channel, live for a member, and the rule's quiet time
// folds the next events into one run that learns their count; (b) a chain of runs,
// each creating a ticket the rule reacts to, stops at depth 3 (`skipped_depth`); (c) a
// page whose review is due is marked in the tree and on the page, its moderator gets
// an activity entry, and "Als geprüft markieren" clears it.
import { expect, test } from "@playwright/test";
import { MEMBER, OWNER, call, pageUrl, publishedPage, signIn, teamSpace } from "./helpers.mjs";
import { ben as benUser, channel, closePages, message, openLive } from "./messaging-helpers.mjs";
import { aiBasics, scriptStub, stubLog } from "./ai-helpers.mjs";
import { chatRequests, levelAgent, member } from "./agents-helpers.mjs";
import {
  advanceClock,
  doneRun,
  dueNow,
  firings,
  loggedTerms,
  makeAutomation,
  onEvent,
  removeAutomations,
  resetClock,
  waitingEvents,
} from "./automations-helpers.mjs";

test.describe.configure({ mode: "serial" });

let anna;
let ben;
let me; // Anna as the API knows her
let kai; // level 2: may create tickets
let space;
const made = []; // automations to remove after each scenario

// System entries in the conversation itself (an open thread repeats its root).
const system = (page, text) =>
  page
    .getByRole("region", { name: "Gespräch" })
    .locator("[data-kind=system]")
    .filter({ hasText: text });
const started = () => `Aufgabe von ${me.name} gestartet.`;
const threadOf = (page, n) =>
  page.getByRole("button", { name: `Thread „${started()}“ öffnen, 1 Antwort` }).nth(n);

test.beforeAll(async ({ browser }) => {
  anna = await browser.newContext();
  me = await signIn(anna, OWNER);
  const { connection } = await aiBasics(anna);
  kai = await levelAgent(anna, "Kai", connection, 2);
  space = await teamSpace(anna, "Redaktion");
  await member(anna, space.id, { type: "agent", id: kai.id }, "editor");
  ben = await browser.newContext();
  await signIn(ben, MEMBER);
});

test.beforeEach(async () => scriptStub(anna.request));

test.afterEach(async () => {
  await closePages(anna, ben);
  await removeAutomations(anna, made.splice(0));
});

test.afterAll(async () => {
  if (anna) await resetClock(anna.request);
  await anna?.close();
  await ben?.close();
});

test("a published page starts a run in the channel; the quiet time folds the next ones into one", async () => {
  const neu = await channel(anna, space.id, "neu");
  const rule = await makeAutomation(anna, {
    agent_id: kai.id,
    place: { type: "channel", conversation_id: neu.id },
    instruction: "Fasse jede neue Seite in einem Satz zusammen.",
    schedule: onEvent("page.published"),
  });
  made.push(rule.id);
  const page = await openLive(ben, `/c/${neu.id}`);
  const thread = page.getByRole("complementary", { name: "Thread" });

  await scriptStub(anna.request, { replies: [{ content: "Neu: der Leitfaden." }] });
  await publishedPage(ben, space.id, "Leitfaden", "Wie wir schreiben.\n"); // Ben's event
  await expect(system(page, started())).toHaveCount(1, { timeout: 30_000 });
  await threadOf(page, 0).click();
  await expect(message(thread, "Kai", "Neu: der Leitfaden.")).toBeVisible();
  const [first] = await loggedTerms(anna, rule.id, 1);
  await doneRun(anna, first.run_id);

  // Within the quiet time two more pages: no run yet, both wait for its end.
  await scriptStub(anna.request, { replies: [{ content: "Zwei weitere Seiten sind neu." }] });
  await publishedPage(ben, space.id, "Glossar", "Begriffe.\n");
  await publishedPage(anna, space.id, "Stilfragen", "Kommas.\n");
  await waitingEvents(rule.id, 2);
  expect(await firings(anna, rule.id)).toHaveLength(1);
  await dueNow(anna, rule.id); // the quiet time's end
  const [, second] = await loggedTerms(anna, rule.id, 2);
  expect(second.outcome).toBe("started");
  await doneRun(anna, second.run_id);
  await expect(system(page, started())).toHaveCount(2, { timeout: 30_000 });
  await threadOf(page, 1).click();
  await expect(message(thread, "Kai", "Zwei weitere Seiten sind neu.")).toBeVisible();
  // The run learnt how many, as a framed note: ids, not the pages' titles or text.
  const [request] = chatRequests(JSON.parse(await stubLog(anna.request)));
  expect(request.text).toContain("events: 2");
  expect(request.text).not.toContain("Kommas.");
});

test("a chain of rules stops at depth 3", async () => {
  const kette = await channel(anna, space.id, "kette");
  const rule = await makeAutomation(anna, {
    agent_id: kai.id,
    place: { type: "channel", conversation_id: kette.id },
    instruction: "Lege zu jedem neuen Ticket ein Folgeticket an.",
    schedule: onEvent("ticket.created"),
  });
  made.push(rule.id);
  await call(anna, "POST", `/api/spaces/${space.id}/tickets`, { title: "Anfang" }); // depth 0
  for (let step = 1; step <= 4; step += 1) {
    await scriptStub(anna.request, {
      replies: [
        {
          tool_calls: [
            { name: "create_ticket", arguments: { space_id: space.id, title: `Folge ${step}` } },
          ],
        },
        { content: `Folge ${step} angelegt.` },
      ],
    });
    if (step > 1) {
      await waitingEvents(rule.id, 1); // the ticket of the step before, in the quiet time
      await dueNow(anna, rule.id);
    }
    // The last run's own ticket is logged at once (too deep), so wait for at least.
    const terms = await loggedTerms(anna, rule.id, step, { atLeast: step === 4 });
    await doneRun(anna, terms[step - 1].run_id);
  }
  // The fourth run's ticket would start a run at depth 4: logged, nothing runs.
  const terms = await loggedTerms(anna, rule.id, 5);
  expect(terms.map((f) => f.outcome)).toEqual([...Array(4).fill("started"), "skipped_depth"]);
  expect(terms[4].run_id).toBeNull();
  const depths = [];
  for (const term of terms.slice(0, 4)) {
    depths.push((await call(anna, "GET", `/api/runs/${term.run_id}`)).chain_depth);
  }
  expect(depths).toEqual([0, 1, 2, 3]);
  const tickets = await call(anna, "GET", `/api/tickets?space_id=${space.id}&limit=100`);
  expect(tickets.items.map((t) => t.title).sort()).toEqual(
    ["Anfang", "Folge 1", "Folge 2", "Folge 3", "Folge 4"].sort(),
  );
  const page = await openLive(anna, `/automations/${rule.id}`);
  const newest = page
    .getByRole("list", { name: "Protokoll der Termine" })
    .getByTestId("firing-row")
    .first();
  await expect(newest).toHaveAttribute("data-outcome", "skipped_depth");
  await expect(newest).toContainText("Übersprungen: Die Kette war zu tief (Tiefe 3)");
});

test("a page due for review is marked, its moderator told, and marking it reviewed clears it", async () => {
  const handbuch = await teamSpace(anna, "Handbuch");
  await member(anna, handbuch.id, { type: "user", id: (await benUser(anna)).id }, "moderator");
  const read = await call(anna, "GET", `/api/spaces/${handbuch.id}`);
  await call(anna, "PATCH", `/api/spaces/${handbuch.id}`, {
    review_interval_days: 7,
    version: read.version,
  });
  const plan = await publishedPage(anna, handbuch.id, "Notfallplan", "Wer ruft wen an.\n");
  const activity = await openLive(ben, "/activity");

  await advanceClock(anna.request, 8 * 24 * 3600); // eight days later: the review is due
  const entry = activity.getByRole("listitem").filter({
    hasText: "Die Prüffrist der Seite „Notfallplan“ ist abgelaufen. Bitte prüfen.",
  });
  await expect(entry).toBeVisible({ timeout: 30_000 });

  const page = await openLive(ben, pageUrl(handbuch, plan));
  const node = page
    .getByRole("tree", { name: "Seiten" })
    .getByRole("treeitem", { name: /Notfallplan/ });
  await expect(node.getByRole("img", { name: "Prüfung fällig" })).toBeVisible();
  const notice = page.getByRole("region", { name: "Prüfung fällig" });
  await expect(notice).toBeVisible();
  await notice.getByRole("button", { name: "Als geprüft markieren" }).click();
  await expect(notice).toHaveCount(0);
  await expect(node.getByRole("img", { name: "Prüfung fällig" })).toHaveCount(0);
  const tree = await call(ben, "GET", `/api/spaces/${handbuch.id}/pages/tree?review_due=true`);
  expect(tree.items ?? tree).toEqual([]);
});
