// Live-editing load for docs/STECKBRIEF.md (plan M9 Task 15): EDITORS people, each with
// a session of their own, edit PAGES pages (EDITORS / PAGES per page) through the API's
// relay `/collab/` with `@hocuspocus/provider`, as the browser does. Each types a word
// every TYPE_MS for SECONDS; every word is timed from sending to its arrival at each
// other editor of its page. Then: were all words stored in the page's Markdown?
//
//   LOAD_PASSWORD=… node collab/scripts/live-load.mjs BASE STATE [SECONDS] [TYPE_MS] \
//     [STOP_PID]
//
// STATE is the file `deploy/compose/loadsetup.py` wrote (one team: its people and pages;
// the people need the role editor there). With STOP_PID, that process (a collab
// instance) gets SIGTERM halfway through the typing; its pages move to another instance
// and the run reports how long the editors were gone and whether anything was lost.
// Prints one JSON object. Words are letters and digits only (nothing the Markdown
// serializer escapes).
import { readFileSync } from "node:fs";
import { HocuspocusProvider } from "@hocuspocus/provider";
import WebSocket from "ws";
import * as Y from "yjs";

const [base, statePath, seconds = "60", typeMs = "500", stopPid = ""] = process.argv.slice(2);
const password = process.env.LOAD_PASSWORD;
if (!base || !statePath || !password) {
  console.error(
    "usage: LOAD_PASSWORD=… node live-load.mjs BASE STATE [SECONDS] [TYPE_MS] [STOP_PID]",
  );
  process.exit(2);
}
const team = JSON.parse(readFileSync(statePath, "utf8")).teams[0];
const origin = new URL(base).origin;
const sentAt = new Map(); // word -> when it was typed
const latencies = [];
const now = () => performance.now();

async function login(email) {
  const response = await fetch(`${base}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "herd" },
    body: JSON.stringify({ email, password }),
  });
  if (response.status !== 200) throw new Error(`login ${email}: ${response.status}`);
  return response.headers.get("set-cookie").split(";")[0];
}

function socketWith(headers) {
  return class extends WebSocket {
    constructor(url, protocols) {
      super(url, protocols, { headers });
      this.on("error", () => {});
    }
  };
}

function paragraph(doc) {
  const fragment = doc.getXmlFragment("default");
  let node = fragment.toArray().findLast((n) => n.nodeName === "paragraph");
  if (!node) {
    node = new Y.XmlElement("paragraph");
    fragment.push([node]);
  }
  let text = node.get(0);
  if (!(text instanceof Y.XmlText)) {
    text = new Y.XmlText();
    node.insert(0, [text]);
  }
  return text;
}

function editor(cookie, pageId, index) {
  const doc = new Y.Doc();
  const seen = new Set();
  const state = { doc, index, pageId, closes: [], synced: false, offlineSince: null, gaps: [] };
  state.provider = new HocuspocusProvider({
    url: `${base.replace(/^http/, "ws")}/collab/${pageId}?generation=0`,
    name: `page:${pageId}`,
    document: doc,
    token: "browser",
    WebSocketPolyfill: socketWith({ origin, cookie }),
    onClose: ({ event }) => {
      state.closes.push(event.code);
      state.offlineSince ??= now();
    },
    onSynced: () => {
      state.synced = true;
      if (state.offlineSince !== null) state.gaps.push(now() - state.offlineSince);
      state.offlineSince = null;
    },
  });
  doc.on("update", (_update, origin) => {
    if (origin === null) return; // own typing
    const tail = paragraph(doc).toString().slice(-600);
    for (const [word] of tail.matchAll(/w\d+x\d+/g)) {
      if (seen.has(word) || !sentAt.has(word) || word.startsWith(`w${index}x`)) continue;
      seen.add(word);
      latencies.push(now() - sentAt.get(word));
    }
  });
  return state;
}

function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length
    ? sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))]
    : null;
}

async function content(cookie, pageId) {
  const response = await fetch(`${base}/api/pages/${pageId}`, { headers: { cookie } });
  return (await response.json()).content_md;
}

const people = team.people;
const pages = team.page_ids;
const cookies = [];
for (const person of people) cookies.push(await login(person.email));
const started = now();
const editors = people.map((_, i) => editor(cookies[i], pages[i % pages.length], i));
while (!editors.every((e) => e.synced)) await new Promise((r) => setTimeout(r, 20));
const connectedMs = now() - started;
const typed = new Map(pages.map((p) => [p, []]));
let sequence = 0;
const timers = editors.map((e) =>
  setInterval(() => {
    if (!e.provider.isSynced && !e.synced) return;
    const word = `w${e.index}x${sequence++}`;
    sentAt.set(word, now());
    typed.get(e.pageId).push(word);
    paragraph(e.doc).insert(paragraph(e.doc).length, ` ${word}`);
  }, Number(typeMs)),
);
let stoppedAt = null;
if (stopPid) {
  setTimeout(
    () => {
      stoppedAt = now();
      process.kill(Number(stopPid), "SIGTERM");
    },
    (Number(seconds) * 1000) / 2,
  );
}
await new Promise((r) => setTimeout(r, Number(seconds) * 1000));
for (const t of timers) clearInterval(t);
// Stored: every word typed on a page is in its Markdown (saves come within 2 to 10 s).
const deadline = now() + 30_000;
let missing = Infinity;
let storedAfterMs = null;
const stopTyping = now();
while (now() < deadline) {
  missing = 0;
  for (const pageId of pages) {
    const markdown = await content(cookies[0], pageId);
    missing += typed.get(pageId).filter((w) => !markdown.includes(w)).length;
  }
  if (missing === 0) {
    storedAfterMs = now() - stopTyping;
    break;
  }
  await new Promise((r) => setTimeout(r, 500));
}
const docsEqual = pages.every((pageId) => {
  const texts = editors.filter((e) => e.pageId === pageId).map((e) => paragraph(e.doc).toString());
  return texts.every((t) => t === texts[0]);
});
const gaps = editors.flatMap((e) => e.gaps);
const round = (v) => (v === null ? null : Math.round(v * 10) / 10);
console.log(
  JSON.stringify({
    editors: editors.length,
    pages: pages.length,
    connected_ms: round(connectedMs),
    words: sequence,
    arrivals: latencies.length,
    latency_ms: {
      p50: round(percentile(latencies, 50)),
      p90: round(percentile(latencies, 90)),
      p99: round(percentile(latencies, 99)),
      max: round(Math.max(...latencies)),
    },
    missing_words: missing,
    stored_after_ms: round(storedAfterMs),
    docs_equal: docsEqual,
    stopped_after_ms: stoppedAt === null ? null : round(stoppedAt - started),
    reconnected: gaps.length,
    reconnect_ms: gaps.length
      ? { p50: round(percentile(gaps, 50)), max: round(Math.max(...gaps)) }
      : null,
    close_codes: [...new Set(editors.flatMap((e) => e.closes))],
  }),
);
for (const e of editors) e.provider.destroy();
process.exit(0);
