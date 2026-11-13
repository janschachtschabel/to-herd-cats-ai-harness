// The heavy checks of live editing off the event loop (review M2 T9): worker threads
// (`check-worker.mjs`) take the work. The answers are those of the functions in
// `check-worker.mjs`.
//
// One queue on this thread; a worker takes one check at a time (review M2 U2, U6):
// - The waiting checks go smallest first (`weight`: about the page's Markdown
//   characters), so a small page does not wait behind large ones. A check that
//   smaller ones have overtaken `maxOvertakes` times goes next, so a large page cannot
//   starve.
// - A worker's heap is capped (`heapMb`): a check that needs more fails with
//   `CheckFailed` instead of taking the whole collab process (and every open live
//   document with it) over its memory limit. Only that check fails; the worker is
//   replaced and the waiting checks run on the new one. The check that killed a worker
//   is not run again: the same page (the same payload) is answered with `CheckFailed`
//   at once, for as long as it is remembered.
// `inlineChecks` does the same work on the calling thread (for tools and tests that
// want no threads).
import { createHash } from "node:crypto";
import { Worker } from "node:worker_threads";
import { WORK } from "./check-worker.mjs";

const SCRIPT = new URL("./check-worker.mjs", import.meta.url);
export const MAX_OVERTAKES = 4;
const REMEMBERED_FAILURES = 200;

/** A check that could not run to its end (its worker ran out of memory or died). */
export class CheckFailed extends Error {}

/** A key for a payload whose check killed a worker (open: Markdown, tidy: bytes). */
function failureKey(kind, payload) {
  if (typeof payload !== "string" && !(payload instanceof Uint8Array)) return null;
  return `${kind}:${createHash("sha256").update(payload).digest("base64")}`;
}

export function createChecks({ workers = 1, heapMb = 192, maxOvertakes = MAX_OVERTAKES } = {}) {
  let sequence = 0;
  let closed = false;
  let restarts = 0;
  const pool = [];
  const queue = []; // waiting checks, oldest first
  const failed = new Map(); // failure keys of checks that killed a worker

  function start(slot) {
    const worker = new Worker(SCRIPT, { resourceLimits: { maxOldGenerationSizeMb: heapMb } });
    const entry = { worker, job: null, dead: false };
    worker.unref();
    worker.on("message", ({ id, result, error }) => {
      const { job } = entry;
      if (!job || job.id !== id) return;
      entry.job = null;
      worker.unref(); // idle: keeps no process alive
      if (error) job.reject(Object.assign(new Error(error.message), { stack: error.stack }));
      else job.resolve(result);
      dispatch();
    });
    const die = (error) => {
      if (entry.dead) return;
      entry.dead = true;
      const { job } = entry;
      entry.job = null;
      if (job) {
        // Only the check it was running fails, and it is not run again.
        if (job.key) {
          failed.set(job.key, true);
          if (failed.size > REMEMBERED_FAILURES) failed.delete(failed.keys().next().value);
        }
        job.reject(new CheckFailed(error.message, { cause: error }));
      }
      if (!closed && pool[slot] === entry) {
        restarts += 1;
        start(slot);
        dispatch();
      }
    };
    worker.on("error", die);
    worker.on("exit", (code) => die(new Error(`check worker exited (${code})`)));
    pool[slot] = entry;
  }

  /** The next check: the oldest once it has been overtaken often enough, else the
   * smallest (the oldest of equal ones). */
  function next() {
    const [oldest] = queue;
    if (oldest.overtaken >= maxOvertakes) return 0;
    let best = 0;
    for (let i = 1; i < queue.length; i++) {
      if (queue[i].weight < queue[best].weight) best = i;
    }
    for (let i = 0; i < best; i++) queue[i].overtaken += 1;
    return best;
  }

  function dispatch() {
    for (const entry of pool) {
      if (queue.length === 0) return;
      if (entry.job || entry.dead) continue;
      const [job] = queue.splice(next(), 1);
      entry.job = job;
      entry.worker.ref(); // a check under way keeps the process alive until answered
      entry.worker.postMessage({ id: job.id, kind: job.kind, payload: job.payload });
    }
  }

  for (let slot = 0; slot < Math.max(1, workers); slot++) start(slot);

  function run(kind, payload, weight) {
    if (closed) return Promise.reject(new CheckFailed("checks closed"));
    const key = failureKey(kind, payload);
    if (key && failed.has(key)) {
      return Promise.reject(new CheckFailed("this check ran a check worker out of memory"));
    }
    return new Promise((resolve, reject) => {
      const id = sequence++;
      queue.push({ id, kind, payload, weight, key, overtaken: 0, resolve, reject });
      dispatch();
    });
  }

  const sizeOf = (payload) => payload?.length ?? 0;

  return {
    /** `liveDocument` and the Yjs state built from it: `{ safe, update, baseline }`.
     * `weight`: the size that orders the queue (default: the Markdown's length). */
    open: (markdown, weight = sizeOf(markdown)) => run("open", markdown, weight),
    /** A stored state as the browser shows it: `{ problem, update, baseline }`. */
    tidy: (stored, weight = sizeOf(stored)) => run("tidy", stored, weight),
    /** The save check (`readback.mjs`). */
    readBack: (json, weight = 0) => run("readBack", json, weight),
    /** How often a worker died and was replaced. */
    get restarts() {
      return restarts;
    },
    async close() {
      closed = true;
      for (const job of queue.splice(0)) job.reject(new CheckFailed("checks closed"));
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
    restarts: 0,
    close: async () => {},
  };
}
