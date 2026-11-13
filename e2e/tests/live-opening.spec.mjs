// Opening a page in the live editor writes nothing (review M2, invariant C; ruling C):
// every page of `pages.mjs` (this repository's Markdown, hostile and targeted pages,
// the collab samples, mutated sections, what the editor itself stores) is opened in
// Chromium, synced and left without typing: two thirds with "Fertig", one third by
// going to the page view. For each page
// - the browser shows exactly the document the server serves after running the
//   browser's editor headless (`collab/settle.mjs`; the agreement of both editors),
// - the browser sends no Yjs update at all (counted at the WebSocket),
// - the stored Markdown is byte-identical, no version is written, also at the end of
//   the run,
// - a page the server refuses (4422) is one the collab process's own check refuses,
//   and is counted and listed.
// At the end the API has counted no load mutation (`herd_collab_load_mutations_total`).
// The leave guard is never armed on these untouched pages (review M4-1 P15): neither
// while the editor connects nor once synced, before it is left (`watchLeaveGuard`), and
// Chromium logs no blocked "beforeunload" prompt.
// A summary goes to test-results/opening-summary.json. HERD_E2E_TABS sets how many tabs
// open pages at once (4).
import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { liveDocument, schema } from "../../collab/markdown.mjs";
import { pages } from "../pages.mjs";
import {
  OWNER,
  call,
  countSentUpdates,
  metric,
  watchLeaveGuard,
  pageUrl,
  publishedPage,
  signIn,
  teamSpace,
} from "./helpers.mjs";

const TABS = Number(process.env.HERD_E2E_TABS || 4);
const INTERNAL_PORT = Number(process.env.HERD_E2E_PORT || 18080) + 1;
const SYNCED = "Synchronisiert";
const STOPPED = "Beendet";
const REFUSED = /nicht unverändert bearbeiten/;

/** The page's status once it has settled: synced, stopped (with the notice) or not. */
async function settledStatus(tab, region) {
  const status = region.getByRole("status");
  const deadline = Date.now() + 30_000;
  for (;;) {
    const text = await status.textContent({ timeout: 1000 }).catch(() => null);
    if (text === SYNCED || text === STOPPED || Date.now() > deadline) return text;
    await tab.waitForTimeout(50);
  }
}

async function openAndLeave(context, tab, space, page, index) {
  const title = `Probe ${index}`;
  const result = { index, group: page.group, name: page.name, length: page.md.length };
  const expected = liveDocument(page.md);
  result.expected = expected.safe ? "opened" : "refused";
  const doc = await publishedPage(context, space.id, title, page.md);
  const versions = await call(context, "GET", `/api/pages/${doc.id}/versions?limit=100`);
  Object.assign(result, { id: doc.id, content: doc.content_md, version: doc.version });
  result.versions = versions.items.length;
  await tab.goto(pageUrl(space, doc, "live"));
  const region = tab.getByRole("region", { name: title });
  const status = await settledStatus(tab, region);
  if (status === STOPPED) {
    const notice = (await region.getByRole("alert").first().textContent()) ?? "";
    result.outcome = REFUSED.test(notice) ? "refused" : `stopped: ${notice.slice(0, 120)}`;
    return result;
  }
  if (status !== SYNCED) {
    result.outcome = `status: ${status}`;
    return result;
  }
  await expect(region.getByRole("textbox")).toHaveAttribute("contenteditable", "true");
  result.outcome = "opened";
  // The browser's editor shows what the server's headless editor settled on.
  const shown = await tab.evaluate(() => document.querySelector(".ProseMirror").editor.getJSON());
  const served = expected.safe ? schema.nodeFromJSON(expected.json).toJSON() : null;
  result.agrees = JSON.stringify(shown) === JSON.stringify(served);
  if (!result.agrees) result.shown = JSON.stringify(shown).slice(0, 400);
  const sentBefore = await tab.evaluate(() => window.__herdSent);
  // Untouched: reloading or closing the tab would not ask, now or at any moment since
  // the page was opened.
  result.armed = await tab.evaluate(() => {
    const armed = window.__herdArmed;
    if (armed.length === 0) return [];
    const statuses = [...new Set(armed.map(({ status }) => status))];
    return [{ times: armed.length, from: armed[0].at, to: armed.at(-1).at, statuses }];
  });
  if (index % 3 === 2) {
    await tab.goto(pageUrl(space, doc));
    result.left = "navigated";
    result.sent = sentBefore;
  } else {
    // "Fertig" asks the server to store everything now: anything the browser changed
    // in the shared document would be saved here.
    await region.getByRole("button", { name: "Fertig" }).click();
    await expect(tab).toHaveURL(new RegExp(`/p/${doc.path}$`));
    result.left = "done";
    result.sent = await tab.evaluate(() => window.__herdSent);
  }
  return result;
}

/** What is wrong with the page now (null: nothing). */
async function stillUnchanged(context, result) {
  const stored = await call(context, "GET", `/api/pages/${result.id}`);
  const versions = await call(context, "GET", `/api/pages/${result.id}/versions?limit=100`);
  if (stored.content_md !== result.content) return "content changed";
  if (stored.version !== result.version) return `version ${result.version} -> ${stored.version}`;
  if (versions.items.length !== result.versions) return "a version was written";
  return null;
}

test("opening a page in the live editor and leaving it changes nothing", async ({ browser }) => {
  test.setTimeout(Number(process.env.HERD_E2E_OPEN_TIMEOUT || 900_000));
  const all = pages();
  if (!process.env.HERD_E2E_GROUPS) expect(all.length).toBeGreaterThanOrEqual(300);
  const context = await browser.newContext();
  await context.addInitScript(countSentUpdates);
  await context.addInitScript(watchLeaveGuard);
  await signIn(context, OWNER);
  const space = await teamSpace(context, "Öffnen");
  const results = [];
  const dialogs = [];
  let next = 0;
  async function worker() {
    const tab = await context.newPage();
    tab.on("dialog", (dialog) => {
      dialogs.push(`${dialog.type()}: ${dialog.message()}`);
      dialog.accept().catch(() => {});
    });
    tab.on("console", (message) => {
      if (message.text().includes("beforeunload")) dialogs.push(message.text().slice(0, 200));
    });
    for (let index = next++; index < all.length; index = next++) {
      try {
        results.push(await openAndLeave(context, tab, space, all[index], index));
      } catch (error) {
        results.push({
          index,
          group: all[index].group,
          name: all[index].name,
          error: String(error).slice(0, 300),
        });
      }
    }
    await tab.close();
  }
  await Promise.all(Array.from({ length: TABS }, worker));
  const problems = [];
  for (const result of results) {
    const where = `${result.group}: ${result.name}`;
    if (result.error) problems.push(`${where}: ${result.error}`);
    else if (result.outcome !== result.expected) {
      problems.push(`${where}: ${result.outcome}, expected ${result.expected}`);
    } else if (result.outcome === "opened") {
      if (result.armed?.length) {
        problems.push(`${where}: the leave guard was armed ${JSON.stringify(result.armed)}`);
      }
      if (!result.agrees) problems.push(`${where}: the browser shows ${result.shown}`);
      const { updates, steps } = result.sent ?? { updates: -1, steps: [] };
      if (updates !== 0 || steps.some((size) => size > 2)) {
        problems.push(`${where}: sent ${updates} updates, sync steps ${steps}`);
      }
    }
    if (result.id) {
      const changed = await stillUnchanged(context, result);
      if (changed) problems.push(`${where}: ${changed}`);
    }
  }
  const loadMutations = await metric(
    context.request,
    INTERNAL_PORT,
    "herd_collab_load_mutations_total",
  );
  const count = (outcome) => results.filter((r) => r.outcome === outcome).length;
  const summary = {
    pages: results.length,
    groups: Object.fromEntries(
      [...new Set(results.map((r) => r.group))].map((g) => [
        g,
        results.filter((r) => r.group === g).length,
      ]),
    ),
    opened: count("opened"),
    refused: results.filter((r) => r.outcome === "refused").map((r) => `${r.group}: ${r.name}`),
    leftWithDone: results.filter((r) => r.left === "done").length,
    leftByNavigating: results.filter((r) => r.left === "navigated").length,
    dialogs,
    guardArmed: results.filter((r) => r.armed?.length).map((r) => `${r.group}: ${r.name}`),
    loadMutations,
    problems,
  };
  mkdirSync("test-results", { recursive: true });
  writeFileSync("test-results/opening-summary.json", JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ ...summary, problems: problems.length }, null, 2));
  expect(problems).toEqual([]);
  expect(dialogs).toEqual([]);
  expect(loadMutations).toBe(0);
  await context.close();
});
