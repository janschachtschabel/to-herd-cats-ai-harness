// The save check over random documents of the editor's schema (review M2 S2, S3; brief
// of fix wave 2): every generated document is written as Markdown that reads back as
// the same document and opens in the live editor again. A fixed seed, so a failure can
// be replayed with `node test/readback-run.mjs <seed> <count>`; a longer run takes
// another seed and count from HERD_GENERATIVE_SEED / HERD_GENERATIVE_COUNT.
import { test } from "node:test";
import assert from "node:assert/strict";
import { runReadBack } from "./readback-run.mjs";

const SEED = Number(process.env.HERD_GENERATIVE_SEED ?? 20261113);
const COUNT = Number(process.env.HERD_GENERATIVE_COUNT ?? 2000);

test(`${COUNT} generated documents pass the save check (seed ${SEED})`, () => {
  const { invalid, failures } = runReadBack(SEED, COUNT);
  assert.equal(invalid, 0, "the generator builds only documents the schema allows");
  const report = [...failures].map(
    ([problem, { count, example }]) => `${count}× ${problem}: ${JSON.stringify(example)}`,
  );
  assert.deepEqual(report, []);
});
