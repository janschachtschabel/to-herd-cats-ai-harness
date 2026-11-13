// The check queue (review M2 U2, U6): a worker that dies fails only the check it was
// running; the checks waiting behind it run on a fresh worker. That check is not run
// again. Waiting checks go smallest first, and a large one is overtaken only a bounded
// number of times.
import { test } from "node:test";
import assert from "node:assert/strict";
import { CheckFailed, createChecks } from "../checks.mjs";

/** A page of tables, heavy to check. */
function tablePage(chars) {
  const blocks = [];
  for (let i = 0; blocks.join("\n\n").length < chars; i++) {
    blocks.push(`## Abschnitt ${i}`, `| Spalte | Wert |\n| --- | ---: |\n| ${i} | ${i * 2} |`);
  }
  return blocks.join("\n\n") + "\n";
}

const page = (words) => `${Array.from({ length: words }, (_, i) => `Wort${i}`).join(" ")}\n`;

test("a worker that dies fails only its own check; the waiting ones run on a fresh one", async () => {
  const checks = createChecks({ heapMb: 32 });
  try {
    const heavy = tablePage(195_000);
    const killer = checks.open(heavy);
    const waiting = ["Eins\n", "Zwei\n", "Drei\n"].map((markdown) => checks.open(markdown));
    await assert.rejects(killer, CheckFailed);
    for (const answer of await Promise.all(waiting)) assert.equal(answer.safe, true);
    // Not run again: answered at once, and no second worker died.
    await assert.rejects(checks.open(heavy), CheckFailed);
    assert.equal((await checks.open("Weiter\n")).safe, true);
    assert.equal(checks.restarts, 1);
  } finally {
    await checks.close();
  }
});

test("waiting checks go smallest first", async () => {
  const checks = createChecks();
  try {
    await checks.open("Start\n"); // the worker is ready: the first check runs at once
    const order = [];
    const track = (name, promise) => promise.then(() => order.push(name));
    const running = track("running", checks.open(page(3000)));
    const big = track("big", checks.open(page(4000)));
    const small = track("small", checks.open(page(10)));
    const middle = track("middle", checks.open(page(500)));
    await Promise.all([running, big, small, middle]);
    assert.deepEqual(order, ["running", "small", "middle", "big"]);
  } finally {
    await checks.close();
  }
});

test("a large check is overtaken only a bounded number of times", async () => {
  const checks = createChecks({ maxOvertakes: 2 });
  try {
    await checks.open("Start\n"); // the worker is ready: the first check runs at once
    const order = [];
    const track = (name, promise) => promise.then(() => order.push(name));
    const all = [track("running", checks.open(page(3000))), track("big", checks.open(page(2000)))];
    for (let i = 0; i < 4; i++) all.push(track(`small${i}`, checks.open(page(5 + i))));
    await Promise.all(all);
    assert.deepEqual(order, ["running", "small0", "small1", "big", "small2", "small3"]);
  } finally {
    await checks.close();
  }
});
