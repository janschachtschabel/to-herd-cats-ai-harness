// The wire protocol of the live connection: close codes, stateless messages,
// presence colours and the connection's grant (shared by live.mjs and server.mjs).

export const CLOSE = {
  generationEnded: [4409, "generation_ended"],
  revoked: [4403, "revoked"],
  forbidden: [4403, "forbidden"],
  unauthorized: [4401, "unauthorized"],
  notFound: [4404, "not_found"],
  tooLarge: [4413, "too_large"],
  saveRefused: [4400, "save_refused"], // the API refused a save for another reason
  notRoundTripSafe: [4422, "collab.not_roundtrip_safe"],
  // The loaded documents hold the memory budget (`memory.mjs`): try again shortly or
  // edit as Markdown (the browser stops, no reconnect loop).
  busy: [4507, "busy"],
  // At the socket (server.mjs): too many connections of one login session or person,
  // no document joined in time, nothing sent for too long (the browser reconnects).
  tooMany: [4429, "too_many_connections"],
  handshakeTimeout: [4408, "handshake_timeout"],
  idle: [4408, "idle_timeout"],
  retry: [1013, "retry"],
};

// Stateless messages: a browser that is done asks for an immediate save (`flush`) and
// is told whether everything it sent is stored (review M2 R3).
export const FLUSH = "herd:flush";
export const SAVED = "herd:saved";
export const UNSAVED = "herd:unsaved";
export const FLUSH_INTERVAL_MS = 1000; // at most one forced save per connection per second
// To every connection of a document: its latest state cannot be stored as Markdown
// (nothing is stored until a later state can be), and that a later state was stored.
// The first is followed by `:<kind>:<where>`: the kind of cause (`structure`, `reopen`,
// `markdown`, `readback.mjs`; `tooLarge`; `timeout`, the check took too long; `unknown`)
// and the index of the top-level block, `<first>-<second>` for two neighbours that fail
// only together, empty if unknown; then `:<detail>` when the kind of difference is known
// (`cause.mjs`).
export const UNREPRESENTABLE = "herd:unrepresentable";

/** The notice for a state that cannot be stored (see UNREPRESENTABLE). */
export function unrepresentableNotice({ kind, block = null, through = null, detail = null }) {
  const where = block === null ? "" : through === null ? `${block}` : `${block}-${through}`;
  return `${UNREPRESENTABLE}:${kind}:${where}${detail ? `:${detail}` : ""}`;
}
export const REPRESENTABLE = "herd:representable";
// To every connection after each successful save: what is stored, as a Yjs snapshot
// (state vector and deletions, base64) after the prefix. A browser whose own changes
// are all in it knows they are stored; one that leaves before is asked first (review M2
// T5). A state that is not stored (refused, or the API answered otherwise) is not sent.
export const STORED = "herd:stored:";
// From a browser whose editor changed the document it had just loaded before the person
// did anything: it stopped instead of sending the change (review M2 ruling B; counted).
export const LOAD_MUTATION = "herd:load-mutation";

// Tailwind's 700 shades: white text on each has at least 4.5:1 (WCAG AA), and the
// browser shows initials in white on them.
const COLORS = ["#1d4ed8", "#be185d", "#15803d", "#b45309", "#6d28d9", "#0e7490", "#b91c1c"];

export function colorFor(id) {
  let hash = 0;
  for (const char of String(id)) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

/** Close the connection's socket (after the protocol message just sent). */
export function closeSocket(context, close) {
  context.closing ??= close; // the first reason stands
  setTimeout(() => context.socket?.close(...context.closing), 0);
}

export function deny(context, close) {
  closeSocket(context, close);
  return Object.assign(new Error(close[1]), { reason: close[1] });
}

/** The grant the API's relay sent (`Authorization: Bearer herd_cg_...`), or null. */
export function readGrant(header) {
  const match = /^Bearer (herd_cg_[A-Za-z0-9_-]{1,92})$/.exec(header ?? "");
  return match ? match[1] : null;
}
