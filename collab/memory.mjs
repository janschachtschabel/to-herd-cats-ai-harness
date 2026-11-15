// The memory budget of loaded documents (review M4-1 P12). A loaded live document costs
// the collab process far more than its stored size: the Y.Doc's structs, the garbage
// V8 keeps until it collects, the copies made on every sync and save. Measured with the
// collab process alone (RSS, one check worker, documents opened at once, 1 to 12):
//
//   page                                  live state   heap (live)  RSS per document
//   13 characters                               62 B        0.3 MB         ~0.3 MB
//   190,000 characters of text                720 KB         10 MB          ~18 MB
//   5,000 table cells (6 × 833)               587 KB       15.5 MB          ~25 MB
//   9,606 table cells (6 × 1,600)            1.1 MB         30 MB          ~45 MB
//
// The heap of a document is about 14 bytes per byte of its live state plus 1.5 KB per
// table cell; RSS grows by about twice that. So the estimate of a document is
// DOCUMENT_BYTES + STATE_FACTOR × live state bytes + CELL_BYTES × table cells, a little
// above what was measured. What is not in it is fixed and paid once: the process with
// an idle check worker (~130 MB) and the check worker's heap at its high-water mark (up
// to its cap of 192 MB, ~250 MB of RSS per check worker). The budget is for documents
// only; the sizing rule is in docs/WIKI.md.
//
// A document past the budget is refused before it is built (4507 "busy"); the first
// document is always taken, so a page larger than the whole budget still opens on an
// otherwise idle process.

export const DOCUMENT_BYTES = 512 * 1024;
export const STATE_FACTOR = 30;
export const CELL_BYTES = 3 * 1024;
export const DEFAULT_BUDGET_MB = 400;
// Before a page is built its live state is not known: about 4 bytes per Markdown
// character and 100 per table cell (190,000 characters: 720 KB; 5,000 cells: 587 KB).
const STATE_BYTES_PER_CHAR = 4;
const STATE_BYTES_PER_CELL = 100;

/** The estimated memory of a loaded document (bytes). */
export function documentEstimate({ stateBytes, cells }) {
  return DOCUMENT_BYTES + STATE_FACTOR * stateBytes + CELL_BYTES * cells;
}

/** The estimate of a page about to be opened, from its stored state (if any) or its
 * Markdown. */
export function pageEstimate({ storedBytes = 0, chars, cells }) {
  const stateBytes = storedBytes || STATE_BYTES_PER_CHAR * chars + STATE_BYTES_PER_CELL * cells;
  return documentEstimate({ stateBytes, cells });
}

export function memoryBudget({ budgetBytes = DEFAULT_BUDGET_MB * 1024 * 1024 } = {}) {
  const held = new Map(); // document name -> estimate (bytes)
  let used = 0;
  let refusals = 0;

  function set(name, bytes) {
    used += bytes - (held.get(name) ?? 0);
    held.set(name, bytes);
  }

  return {
    budgetBytes,
    /** Take `bytes` for the document; false (and counted) when the budget would be
     * exceeded while other documents are loaded. */
    reserve(name, bytes) {
      const others = used - (held.get(name) ?? 0);
      if (others > 0 && others + bytes > budgetBytes) {
        refusals += 1;
        return false;
      }
      set(name, bytes);
      return true;
    },
    /** The estimate of a loaded document, once measured. */
    settle(name, bytes) {
      if (held.has(name)) set(name, bytes);
    },
    /** The document was unloaded (or not loaded after all). */
    release(name) {
      used -= held.get(name) ?? 0;
      held.delete(name);
    },
    get used() {
      return used;
    },
    get refusals() {
      return refusals;
    },
  };
}

/** The budget's numbers for Prometheus (text format 0.0.4). */
export function metricsText(memory, documents) {
  const lines = [];
  const metric = (name, type, help, value) =>
    lines.push(`# HELP ${name} ${help}`, `# TYPE ${name} ${type}`, `${name} ${value}`);
  metric(
    "herd_collab_memory_estimate_bytes",
    "gauge",
    "Estimated memory held by the loaded live documents (memory.mjs).",
    memory.used,
  );
  metric(
    "herd_collab_memory_budget_bytes",
    "gauge",
    "Budget for the loaded live documents (HERD_COLLAB_MEMORY_BUDGET_MB).",
    memory.budgetBytes,
  );
  metric(
    "herd_collab_memory_refusals_total",
    "counter",
    "Pages not opened because the loaded documents hold the budget (4507 busy).",
    memory.refusals,
  );
  metric(
    "herd_collab_documents",
    "gauge",
    "Live documents loaded in the collab process.",
    documents,
  );
  return `${lines.join("\n")}\n`;
}
