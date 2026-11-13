// Setting up through the API, and signing a browser context in, as the SPA does.
import { expect } from "@playwright/test";
import { OWNER } from "../global-setup.mjs";

export { OWNER };
export const MEMBER = { email: "ben@e2e.example", password: "e2e-password-456", name: "Ben" };
const HEADERS = { "X-Requested-With": "herd" };

/** Signs the context in: its requests and its pages share the session cookie. */
export async function signIn(context, { email, password }) {
  const r = await context.request.post("/api/auth/login", {
    data: { email, password },
    headers: HEADERS,
  });
  expect(r.status(), await r.text()).toBe(200);
  return (await r.json()).user;
}

export async function call(context, method, path, data) {
  const r = await context.request.fetch(path, { method, data, headers: HEADERS });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? null : r.json();
}

/** A team space with Ben as an editor; created once per run. */
export async function teamSpace(context, name) {
  const space = await call(context, "POST", "/api/spaces", { name, kind: "team" });
  const users = await call(context, "GET", "/api/admin/users?limit=100");
  let ben = users.items.find((u) => u.email === MEMBER.email);
  ben ??= await call(context, "POST", "/api/admin/users", MEMBER);
  await call(context, "PUT", `/api/spaces/${space.id}/members`, {
    member_type: "user",
    member_id: ben.id,
    role: "editor",
  });
  return space;
}

export async function publishedPage(context, spaceId, title, content_md) {
  const page = await call(context, "POST", `/api/spaces/${spaceId}/pages`, { title, content_md });
  return call(context, "POST", `/api/pages/${page.id}/publish`, { version: page.version });
}

export const pageUrl = (space, page, view) =>
  `/spaces/${space.id}/p/${page.path}${view ? `?view=${view}` : ""}`;

/** Counts what the browser sends of the shared document (in the page): Yjs updates
 * (`updates`) and the size of each sync step 2 (an empty one is 2 bytes). */
export function countSentUpdates() {
  window.__herdSent = { updates: 0, steps: [] };
  const send = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    try {
      const bytes =
        data instanceof ArrayBuffer ? new Uint8Array(data) : new Uint8Array(data.buffer ?? []);
      let at = 0;
      const uint = () => {
        let value = 0;
        let shift = 0;
        for (;;) {
          const byte = bytes[at++];
          value += (byte & 0x7f) * 2 ** shift;
          shift += 7;
          if (byte < 0x80) return value;
        }
      };
      const nameLength = uint();
      at += nameLength; // the document's name
      const type = uint();
      if (type === 0 || type === 4) {
        const step = uint();
        if (step === 2) window.__herdSent.updates += 1;
        if (step === 1) window.__herdSent.steps.push(uint());
      }
    } catch {
      // not a message of the document
    }
    return send.call(this, data);
  };
}

/** The value of a counter on the internal port's /metrics (0 when absent). */
export async function metric(request, port, line) {
  const text = await (await request.get(`http://127.0.0.1:${port}/metrics`)).text();
  const found = text.split("\n").find((l) => l.startsWith(`${line} `));
  return found ? Number(found.split(" ").at(-1)) : 0;
}

/** Watches the leave guard (in the page, review M4-1 P15): every 20 ms a synthetic
 * `beforeunload` is dispatched; one that a handler cancels means reloading or closing
 * the tab would ask now. Each armed moment is recorded with the editor's status
 * (`window.__herdArmed`). Headless Chromium does not show the prompt itself (it logs
 * "Blocked attempt to show a 'beforeunload' confirmation panel"), so this is the way
 * to see it. */
export function watchLeaveGuard() {
  window.__herdArmed = [];
  setInterval(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    if (!event.defaultPrevented) return;
    const status = document.querySelector("[role=status]")?.textContent ?? null;
    window.__herdArmed.push({ at: Math.round(performance.now()), status });
  }, 20);
}
