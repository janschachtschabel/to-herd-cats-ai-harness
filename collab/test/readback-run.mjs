// Runs the save check (`readback.mjs`) over generated documents and groups the
// failures. Used by the test (fixed seed, 2,000 documents) and by hand for longer runs:
//   node test/readback-run.mjs <seed> <count>
import { editorProblem } from "../markdown.mjs";
import { readBack } from "../readback.mjs";
import { generateDocument, seeded } from "./generate.mjs";

/** `{ documents, invalid, failures: Map<class, { count, example }> }`. */
export function runReadBack(seed, count) {
  const random = seeded(seed);
  const failures = new Map();
  let invalid = 0;
  for (let i = 0; i < count; i++) {
    const json = generateDocument(random);
    if (editorProblem(json) !== null) {
      invalid++; // the generator built something the schema does not allow
      continue;
    }
    let result;
    try {
      result = readBack(json);
    } catch (error) {
      result = { ok: false, problem: `throws: ${error.message}` };
    }
    if (result.ok) continue;
    const key = result.problem.replace(/\d+/g, "N");
    const entry = failures.get(key) ?? { count: 0, example: null };
    entry.count++;
    const size = JSON.stringify(json).length;
    if (!entry.example || size < entry.size) Object.assign(entry, { example: json, size });
    failures.set(key, entry);
  }
  return { documents: count, invalid, failures };
}

if (process.argv[1]?.endsWith("readback-run.mjs")) {
  const seed = Number(process.argv[2] ?? 20261113);
  const count = Number(process.argv[3] ?? 2000);
  const started = Date.now();
  const { invalid, failures } = runReadBack(seed, count);
  const failed = [...failures.values()].reduce((sum, entry) => sum + entry.count, 0);
  console.log(`seed ${seed}: ${count} documents, ${invalid} invalid, ${failed} failed`);
  console.log(`(${((Date.now() - started) / 1000).toFixed(1)} s)`);
  for (const [key, { count: n, example }] of [...failures].sort(
    (a, b) => b[1].count - a[1].count,
  )) {
    console.log(`${n}× ${key}\n   ${JSON.stringify(example)}`);
  }
}
