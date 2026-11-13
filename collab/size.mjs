// The size of a live document between saves (review M2 R9, S5). The API refuses a
// save over 5 MiB of state or 200,000 characters of Markdown; without a cap here a
// document could grow far beyond that in the seconds between two saves. Each
// incoming update is checked before it is applied: a cheap estimate (the last
// measurement plus what the updates since could add) and, only when that crosses a
// limit, an exact measurement of the document as it would be with the update (at most
// once a second per document; an update that needs another measurement within that
// second waits until the second is over, review M2 T12). An update that would cross
// it is refused (its sender is closed with 4413); the document and everyone else stay
// as they were.
import * as Y from "yjs";
import { yDocToMarkdown } from "./markdown.mjs";

export const MAX_STATE_BYTES = 5 * 1024 * 1024;
// A message carries at most the whole state (a joining browser gets it in one) and its
// envelope. The API's relay passes exactly this much (`backend/app/web/collab_proxy.py`
// derives it from the API's own state cap; a backend test checks both agree, review M2
// U3): before, it passed 1 MiB and a large table page never opened.
export const MESSAGE_ENVELOPE_BYTES = 64 * 1024;
export const MAX_MESSAGE_BYTES = MAX_STATE_BYTES + MESSAGE_ENVELOPE_BYTES;
export const MAX_MARKDOWN_CHARS = 200_000;
// Markdown characters one byte of a Yjs update can add, generously (a character next
// to a delimiter written as a reference, `&#x54;`, is six for one): the estimate only
// decides when to measure exactly.
const CHARS_PER_BYTE = 8;
const MEASURE_EVERY_MS = 1000;

const SYNC = 0;
const SYNC_REPLY = 4;
const STEP_2 = 1;
const UPDATE = 2;

function readVarUint(bytes, at) {
  let value = 0;
  let shift = 0;
  while (at.i < bytes.length) {
    const byte = bytes[at.i++];
    value += (byte & 0x7f) * 2 ** shift;
    if (byte < 0x80) return value;
    shift += 7;
  }
  return -1;
}

/** The Yjs update a raw Hocuspocus message carries (a sync step 2 or an update), or
 * null for awareness, auth and stateless messages. */
export function contentOf(raw) {
  const at = { i: 0 };
  const nameLength = readVarUint(raw, at);
  if (nameLength < 0) return null;
  at.i += nameLength;
  const type = readVarUint(raw, at);
  if (type !== SYNC && type !== SYNC_REPLY) return null;
  const step = readVarUint(raw, at);
  if (step !== STEP_2 && step !== UPDATE) return null;
  const length = readVarUint(raw, at);
  if (length < 0 || at.i + length > raw.length) return null;
  return raw.subarray(at.i, at.i + length);
}

export function sizeGuard({
  maxStateBytes = MAX_STATE_BYTES,
  maxMarkdownChars = MAX_MARKDOWN_CHARS,
  measureEveryMs = MEASURE_EVERY_MS,
}) {
  function measure(document) {
    return {
      bytes: Y.encodeStateAsUpdate(document).length,
      chars: yDocToMarkdown(document).length,
    };
  }

  const over = (size, bytes) =>
    size.bytes + bytes > maxStateBytes || size.chars + bytes * CHARS_PER_BYTE > maxMarkdownChars;

  /** The size of the document with the update applied, measured on a copy. */
  function measureWith(document, update) {
    const copy = new Y.Doc({ gc: false });
    try {
      Y.applyUpdate(copy, Y.encodeStateAsUpdate(document));
      Y.applyUpdate(copy, update);
      return measure(copy);
    } finally {
      copy.destroy();
    }
  }

  return {
    measure,
    /** Whether a measured size is within the limits. */
    fits: (size) => size.bytes <= maxStateBytes && size.chars <= maxMarkdownChars,
    /** False when the raw message must be refused; keeps `state.size` current. A
     * message that needs a measurement waits for its turn (one per interval and
     * document): Hocuspocus takes a connection's messages one after the other. */
    async admit(document, state, raw) {
      const update = contentOf(raw);
      if (update === null) return true;
      if (over(state.size, update.length)) {
        // Measuring copies and writes out the whole document: at most once per
        // interval and document (review M2 S10); an update needing more waits for the
        // interval's end (T12).
        const turn = (state.measuring ?? Promise.resolve()).then(async () => {
          const wait = (state.measuredAt ?? -Infinity) + measureEveryMs - Date.now();
          // Always a turn of the event loop: the update before is applied by then.
          await new Promise((resolve) => setTimeout(resolve, Math.max(0, wait)));
          state.measuredAt = Date.now();
          let size;
          try {
            size = measureWith(document, update);
          } catch {
            return true; // not an update Yjs can apply: Hocuspocus deals with it
          }
          if (size.bytes > maxStateBytes || size.chars > maxMarkdownChars) return false;
          state.size = size;
          return true;
        });
        state.measuring = turn;
        return turn;
      }
      state.size = {
        bytes: state.size.bytes + update.length,
        chars: state.size.chars + update.length * CHARS_PER_BYTE,
      };
      return true;
    },
  };
}
