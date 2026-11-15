// The table cell cap (review M2 U2): a page whose tables hold more than MAX_TABLE_CELLS
// cells is too large for live editing. A cheap count refuses it before a check worker
// is asked (such tables ran a worker out of memory): opening is closed with 4413, a
// state over the cap is not stored and everyone is told it is too large.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { MAX_TABLE_CELLS, jsonTableCells, markdownTableCells } from "../cells.mjs";
import { inlineChecks } from "../checks.mjs";
import { markdownToJSON } from "../markdown.mjs";
import { UNREPRESENTABLE } from "../protocol.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

/** A table of `columns` × `rows` body rows of `x`. */
function table(columns, rows) {
  const line = (cell) => `| ${Array(columns).fill(cell).join(" | ")} |`;
  return [line("h"), line("---"), ...Array(rows).fill(line("x"))].join("\n");
}

test("the cap is 5,000 cells (review M4-1 P12: a table page of 9,606 cells held ~30 MB)", () => {
  assert.equal(MAX_TABLE_CELLS, 5_000);
});

test("the Markdown count is the parser's count", () => {
  const cases = [
    "Text ohne Tabelle\n",
    table(3, 4),
    `# T\n\n${table(2, 3)}\n\nText\n\n${table(4, 1)}\n`,
    "| a | b |\n| --- | --- |\n| 1 |\n| 1 | 2 | 3 |\n", // ragged: as wide as its widest row
    "| a \\| b | c |\n| --- | --- |\n| `x\\|y` | z |\n", // escaped pipes
    "```\n| a | b |\n| - | - |\n| 1 | 2 |\n```\n", // in code: no table
    "> | a | b |\n> | - | - |\n> | 1 | 2 |\n", // in a quote
    "- Punkt\n\n  | a | b |\n  | - | - |\n  | 1 | 2 |\n", // in a list item
    "| a |\n| - |\n| 1 |\nweiter\n\n", // a lazy row
    "a | b\n-- | --\n1 | 2\n", // without outer pipes
    "a | b\n- | -\n1 | 2\n", // a list item, not a delimiter row
  ];
  for (const markdown of cases) {
    assert.equal(markdownTableCells(markdown), jsonTableCells(markdownToJSON(markdown)), markdown);
  }
});

test("a page over the cap is refused at once, without a check", async () => {
  const markdown = `# Inventar\n\n${table(10, MAX_TABLE_CELLS / 10)}\n`; // header row: over
  assert.ok(markdownTableCells(markdown) > MAX_TABLE_CELLS);
  const checks = inlineChecks();
  let asked = 0;
  for (const kind of ["open", "tidy", "readBack"]) {
    const work = checks[kind];
    checks[kind] = (...args) => {
      asked++;
      return work(...args);
    };
  }
  live = await liveFixture({ markdown, createCollabServer, checks });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await until(() => anna.closes.includes(4413));
  assert.equal(asked, 0, "no check worker was asked");
  assert.equal(live.api.saves.length, 0);
});

test("a page at the cap opens", async () => {
  const markdown = table(10, MAX_TABLE_CELLS / 10 - 1);
  assert.equal(markdownTableCells(markdown), MAX_TABLE_CELLS);
  live = await liveFixture({ markdown, createCollabServer, checkWorkers: 0 });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  assert.deepEqual(anna.closes, []);
});

test("a state over the cap is not stored, and everyone is told it is too large", async () => {
  const markdown = `Text\n\n${table(10, MAX_TABLE_CELLS / 10 - 1)}\n`;
  live = await liveFixture({ markdown, createCollabServer, checkWorkers: 0 });
  const anna = live.open({ cookie: "herd_session=token-a" });
  await synced(anna);
  const heard = [];
  anna.provider.on("stateless", ({ payload }) => heard.push(payload));
  const stored = live.api.saves.length;
  // One more row: ten cells over the cap.
  const fragment = anna.doc.getXmlFragment("default");
  const rows = fragment.get(1);
  rows.insert(rows.length, [rows.get(rows.length - 1).clone()]);
  await until(() => heard.includes(`${UNREPRESENTABLE}:tooLarge:1`), 8000);
  assert.equal(live.api.saves.length, stored);
  assert.deepEqual(anna.closes, [], "the session goes on: the row can be taken out again");
});
