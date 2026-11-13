// The size of a live document between saves (review M2 R9). The API refuses a save
// over 5 MiB of state or 200,000 characters of Markdown; without a cap here a
// document could grow far beyond that in the seconds between two saves. Each
// incoming update is checked before it is applied: a cheap estimate (the last
// measurement plus what arrived since) and, only when that crosses a limit, an exact
// measurement. An update that would still cross it is refused (its sender is closed
// with 4413); the document and everyone else stay as they were.
import * as Y from "yjs";
import { yDocToMarkdown } from "./markdown.mjs";

export const MAX_STATE_BYTES = 5 * 1024 * 1024;
export const MAX_MARKDOWN_CHARS = 200_000;
// Markdown characters one byte of a Yjs update can add at most (markup per element,
// e.g. "- " for an empty list item of a few bytes), as an estimate.
const CHARS_PER_BYTE = 2;

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

/** Whether a raw Hocuspocus message carries document content (a sync step 2 or an
 * update); awareness, auth and stateless messages do not. */
export function carriesContent(raw) {
  const at = { i: 0 };
  const nameLength = readVarUint(raw, at);
  if (nameLength < 0) return false;
  at.i += nameLength;
  const type = readVarUint(raw, at);
  if (type !== SYNC && type !== SYNC_REPLY) return false;
  const step = readVarUint(raw, at);
  return step === STEP_2 || step === UPDATE;
}

export function sizeGuard({
  maxStateBytes = MAX_STATE_BYTES,
  maxMarkdownChars = MAX_MARKDOWN_CHARS,
}) {
  function measure(document) {
    return {
      bytes: Y.encodeStateAsUpdate(document).length,
      chars: yDocToMarkdown(document).length,
    };
  }

  const over = (size, bytes) =>
    size.bytes + bytes > maxStateBytes || size.chars + bytes * CHARS_PER_BYTE > maxMarkdownChars;

  return {
    measure,
    /** False when the update of `bytes` must be refused; keeps `state.size` current. */
    admit(document, state, bytes) {
      if (over(state.size, bytes)) {
        state.size = measure(document);
        if (over(state.size, bytes)) return false;
      }
      state.size = {
        bytes: state.size.bytes + bytes,
        chars: state.size.chars + bytes * CHARS_PER_BYTE,
      };
      return true;
    },
  };
}
