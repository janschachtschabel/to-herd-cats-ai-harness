// What the collab process's HTTP port admits (`server.mjs`): the Origin check, the
// connection counters and refusing an upgrade; and its log lines.

function hostOf(value) {
  try {
    return new URL(value).host.toLowerCase();
  } catch {
    return null;
  }
}

/** The Origin header must be HERD_PUBLIC_URL's origin; without one, the host the
 * browser connected to (the relay and ingresses forward it as X-Forwarded-Host). */
export function originAllowed(headers, publicUrl) {
  const origin = headers.origin;
  if (!origin) return false;
  if (publicUrl) return origin === new URL(publicUrl).origin;
  const forwarded = headers["x-forwarded-host"]?.split(",")[0].trim();
  const host = (forwarded || headers.host || "").toLowerCase();
  return host !== "" && hostOf(origin) === host;
}

/** Counts per key (login session, session and page); `take` is false at the limit. */
export function counter() {
  const counts = new Map();
  return {
    take(key, limit) {
      const count = counts.get(key) ?? 0;
      if (count >= limit) return false;
      counts.set(key, count + 1);
      return true;
    },
    give(key) {
      const count = (counts.get(key) ?? 1) - 1;
      if (count > 0) counts.set(key, count);
      else counts.delete(key);
    },
  };
}

export function refuse(socket, status) {
  socket.end(`HTTP/1.1 ${status} Refused\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
}

export function logger(fields) {
  return (message, extra = {}) =>
    console.log(
      JSON.stringify({ timestamp: new Date().toISOString(), message, ...fields, ...extra }),
    );
}
