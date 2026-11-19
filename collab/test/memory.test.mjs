// The memory budget of loaded documents (review M4-1 P12): a few editors opening large
// pages took the collab process over its memory limit, and every live session of every
// person dropped with it. The process keeps an estimate of what its loaded documents
// hold and refuses to load one more past HERD_COLLAB_MEMORY_BUDGET_MB (4507 "busy": the
// browser stops and offers the Markdown editor, nothing is stored). A document is
// unloaded, and its estimate given back, once the last person leaves. `/metrics` shows
// the estimate, the budget and the refusals.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { memoryBudget, documentEstimate } from "../memory.mjs";
import { createCollabServer } from "../server.mjs";
import { liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

const MB = 1024 * 1024;
const table = (columns, rows) => {
  const line = (cell) => `| ${Array(columns).fill(cell).join(" | ")} |`;
  return [line("h"), line("---"), ...Array(rows).fill(line("x"))].join("\n") + "\n";
};

test("the estimate grows with the live state's bytes and the table cells", () => {
  const small = documentEstimate({ stateBytes: 100, cells: 0 });
  const text = documentEstimate({ stateBytes: 720_000, cells: 0 });
  const tables = documentEstimate({ stateBytes: 587_000, cells: 5_000 });
  assert.ok(small < 1 * MB, `${small}`);
  // Measured (heap and the garbage V8 keeps before collecting, about twice the live
  // heap): a 190,000-character text page ~18 MB of RSS, a 5,000-cell table page ~25 MB.
  assert.ok(text > 18 * MB && text < 30 * MB, `${text / MB}`);
  assert.ok(tables > 25 * MB && tables < 40 * MB, `${tables / MB}`);
});

test("a document past the budget is refused; the first one is always taken", () => {
  const budget = memoryBudget({ budgetBytes: 50 * MB });
  assert.equal(budget.reserve("page:a", 60 * MB), true); // nothing else loaded
  assert.equal(budget.reserve("page:b", 1 * MB), false);
  assert.equal(budget.refusals, 1);
  budget.release("page:a");
  assert.equal(budget.used, 0);
  assert.equal(budget.reserve("page:b", 30 * MB), true);
  assert.equal(budget.reserve("page:c", 20 * MB), true); // exactly at the budget
  assert.equal(budget.reserve("page:d", 1), false);
  budget.settle("page:c", 10 * MB); // measured after loading: smaller
  assert.equal(budget.used, 40 * MB);
  assert.equal(budget.reserve("page:d", 10 * MB), true);
});

test("a page past the budget is refused as busy, alone, and opens once others leave", async () => {
  const other = "01a1d2d9-2de5-75db-9dc6-a6fa13072701";
  live = await liveFixture({
    markdown: table(6, 800),
    createCollabServer,
    memoryBudgetBytes: 1, // only the first document fits
  });
  live.api.pages[other] = table(6, 799);
  const anna = live.open({ grant: "herd_cg_a" });
  await synced(anna);
  const ben = live.open({ grant: "herd_cg_b", name: `page:${other}` }, { page: other });
  await until(() => ben.closes.length > 0);
  assert.equal(ben.closes[0], 4507);
  ben.destroy(); // a browser stops on 4507 (no reconnect loop; frontend liveSession)
  const savesOfOther = () => live.api.saves.filter((save) => save.content_md === table(6, 799));
  assert.equal(savesOfOther().length, 0); // refused before anything was built or stored
  assert.deepEqual(anna.closes, []);
  const metrics = await (await fetch(live.metricsUrl)).text();
  assert.match(metrics, /^herd_collab_memory_refusals_total 1$/m);
  assert.match(metrics, /^herd_collab_memory_budget_bytes 1$/m);
  const estimate = Number(/^herd_collab_memory_estimate_bytes (\d+)$/m.exec(metrics)[1]);
  assert.ok(estimate > 5 * MB, `${estimate}`);
  assert.match(metrics, /^herd_collab_documents 1$/m);
  // Anna leaves: her document is unloaded and its estimate given back.
  anna.destroy();
  await until(async () =>
    /^herd_collab_documents 0$/m.test(await (await fetch(live.metricsUrl)).text()),
  );
  assert.match(
    await (await fetch(live.metricsUrl)).text(),
    /^herd_collab_memory_estimate_bytes 0$/m,
  );
  const again = live.open({ grant: "herd_cg_b", name: `page:${other}` }, { page: other });
  await synced(again);
});
