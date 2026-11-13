// The wire protocol of the live connection: close codes, stateless messages,
// presence colours and the cookie (shared by live.mjs and server.mjs).

export const CLOSE = {
  generationEnded: [4409, "generation_ended"],
  revoked: [4403, "revoked"],
  forbidden: [4403, "forbidden"],
  unauthorized: [4401, "unauthorized"],
  notFound: [4404, "not_found"],
  tooLarge: [4413, "too_large"],
  saveRefused: [4400, "save_refused"], // the API refused a save for another reason
  notRoundTripSafe: [4422, "collab.not_roundtrip_safe"],
  // At the socket (server.mjs): too many connections of one login session, no
  // document joined in time.
  tooMany: [4429, "too_many_connections"],
  handshakeTimeout: [4408, "handshake_timeout"],
  retry: [1013, "retry"],
};

// Stateless messages: a browser that is done asks for an immediate save (`flush`) and
// is told whether everything it sent is stored (review M2 R3).
export const FLUSH = "herd:flush";
export const SAVED = "herd:saved";
export const UNSAVED = "herd:unsaved";
export const FLUSH_INTERVAL_MS = 1000; // at most one forced save per connection per second

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

export function readCookie(header, name) {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index > 0 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return null;
}
