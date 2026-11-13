// The heavy checks of live editing off the event loop (review M2 T9): worker threads
// (`check-worker.mjs`) take the work, each request goes to the one with the fewest
// waiting. The answers are those of the functions in `check-worker.mjs`.
//
// A worker's heap is capped (`heapMb`): a page that needs more to be checked fails
// with `CheckFailed` instead of taking the whole collab process (and every open live
// document with it) over its memory limit. A worker that dies fails its waiting
// requests and is replaced. `inlineChecks` does the same work on the calling thread
// (for tools and tests that want no threads).
import { Worker } from "node:worker_threads";
import { WORK } from "./check-worker.mjs";

const SCRIPT = new URL("./check-worker.mjs", import.meta.url);

/** A check that could not run to its end (its worker ran out of memory or died). */
export class CheckFailed extends Error {}

export function createChecks({ workers = 1, heapMb = 192 } = {}) {
  let next = 0;
  let closed = false;
  const pool = [];

  function start(slot) {
    const worker = new Worker(SCRIPT, { resourceLimits: { maxOldGenerationSizeMb: heapMb } });
    const entry = { worker, waiting: new Map() };
    worker.unref();
    worker.on("message", ({ id, result, error }) => {
      const request = entry.waiting.get(id);
      if (!request) return;
      entry.waiting.delete(id);
      if (error) request.reject(Object.assign(new Error(error.message), { stack: error.stack }));
      else request.resolve(result);
    });
    let failed = false;
    const fail = (error) => {
      if (failed) return;
      failed = true;
      for (const request of entry.waiting.values()) {
        request.reject(new CheckFailed(error.message, { cause: error }));
      }
      entry.waiting.clear();
      if (!closed && pool[slot] === entry) start(slot);
    };
    worker.on("error", fail);
    worker.on("exit", (code) => fail(new Error(`check worker exited (${code})`)));
    pool[slot] = entry;
  }

  for (let slot = 0; slot < Math.max(1, workers); slot++) start(slot);

  function run(kind, payload) {
    if (closed) return Promise.reject(new CheckFailed("checks closed"));
    const entry = pool.reduce((best, e) => (e.waiting.size < best.waiting.size ? e : best));
    const id = next++;
    return new Promise((resolve, reject) => {
      entry.waiting.set(id, { resolve, reject });
      entry.worker.postMessage({ id, kind, payload });
    });
  }

  return {
    /** `liveDocument` and the Yjs state built from it: `{ safe, update, baseline }`. */
    open: (markdown) => run("open", markdown),
    /** A stored state as the browser shows it: `{ problem, update, baseline }`. */
    tidy: (stored) => run("tidy", stored),
    /** The save check (`readback.mjs`). */
    readBack: (json) => run("readBack", json),
    async close() {
      closed = true;
      await Promise.all(pool.map(({ worker }) => worker.terminate()));
    },
  };
}

/** The same checks on the calling thread. */
export function inlineChecks() {
  const run = async (kind, payload) => WORK[kind](payload);
  return {
    open: (markdown) => run("open", markdown),
    tidy: (stored) => run("tidy", stored),
    readBack: (json) => run("readBack", json),
    close: async () => {},
  };
}
