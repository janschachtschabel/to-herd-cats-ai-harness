// End to end: the real API (`python -m app.launch`, HERD_ROLE=all, which starts this
// collab process as its child) on a scratch database, two browser-like Yjs clients
// through the relay `/collab`. Covers the review focus "stale live session" and
// "rights revocation". Needs PostgreSQL, uv and psql; runs only with
// HERD_COLLAB_INTEGRATION=1 (`npm run test:integration`).
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { yDocToMarkdown } from "../markdown.mjs";
import { client, synced, type, until } from "./helpers.mjs";
import { INTERNAL_TOKEN, PASSWORD, enabled, startBackend } from "./integration-backend.mjs";

let it;
let api;
let login;
let open;
let content;
let collabBase;
let internalBase;
const clients = [];

before(async () => {
  if (!enabled) return;
  it = await startBackend();
  ({ api, login, open, content, collabBase, internalBase } = it);
});

after(async () => {
  if (!enabled) return;
  for (const c of clients) c.destroy();
  await it?.stop();
});

test(
  "two browsers edit live; a Markdown save and a revoked right end it cleanly",
  { skip: !enabled, timeout: 180_000 },
  async () => {
    const owner = await login("owner@it.example");
    const created = await api("/api/admin/users", {
      method: "POST",
      cookie: owner.cookie,
      body: { email: "member@it.example", name: "Mitglied", password: PASSWORD },
    });
    assert.equal(created.status, 201, JSON.stringify(created.body));
    const member = await login("member@it.example");
    const space = (
      await api("/api/spaces", {
        method: "POST",
        cookie: owner.cookie,
        body: { name: "Live", kind: "team" },
      })
    ).body;
    const role = (r) => ({ member_type: "user", member_id: member.user.id, role: r });
    await api(`/api/spaces/${space.id}/members`, {
      method: "PUT",
      cookie: owner.cookie,
      body: role("editor"),
    });
    let page = (
      await api(`/api/spaces/${space.id}/pages`, {
        method: "POST",
        cookie: owner.cookie,
        body: { title: "Live", content_md: "# Start" },
      })
    ).body;
    page = (
      await api(`/api/pages/${page.id}/publish`, {
        method: "POST",
        cookie: owner.cookie,
        body: { version: page.version },
      })
    ).body;

    // Two browsers, one document.
    const a = open(owner.cookie, page.id, 0);
    const b = open(member.cookie, page.id, 0);
    await Promise.all([synced(a), synced(b)]);
    assert.equal(yDocToMarkdown(a.doc), "# Start");
    type(a.doc, "Hallo von A");
    await until(() => yDocToMarkdown(b.doc).includes("Hallo von A"));
    type(b.doc, " und B");
    await until(
      async () =>
        (await content(owner.cookie, page.id)).content_md === "# Start\n\nHallo von A und B",
      15_000,
    );
    const versions = (await api(`/api/pages/${page.id}/versions`, { cookie: owner.cookie })).body
      .items;
    assert.ok(
      versions.some((v) => v.source === "collab"),
      JSON.stringify(versions),
    );

    // Rights revocation: Mitglied becomes a viewer while typing.
    await api(`/api/spaces/${space.id}/members`, {
      method: "PUT",
      cookie: owner.cookie,
      body: role("viewer"),
    });
    type(b.doc, " nach dem Entzug");
    await until(() => b.closes.includes(4403), 15_000);
    // The unsaved state held B's edit: the generation ends, so A's browser, which saw
    // the edit, cannot bring it back by reconnecting (its provider keeps trying).
    await until(() => a.closes.includes(4409), 15_000);
    await new Promise((resolve) => setTimeout(resolve, 4000));
    page = await content(owner.cookie, page.id);
    assert.equal(page.content_md, "# Start\n\nHallo von A und B");
    assert.equal(page.collab_generation, 1);
    a.destroy();
    b.destroy();

    // Stale live session: a Markdown save ends the generation.
    const live = open(owner.cookie, page.id, page.collab_generation);
    await synced(live);
    const patched = await api(`/api/pages/${page.id}`, {
      method: "PATCH",
      cookie: owner.cookie,
      body: { content_md: "# Markdown-Modus", version: page.version },
    });
    assert.equal(patched.status, 200, JSON.stringify(patched.body));
    type(live.doc, "alter Stand");
    await until(() => live.closes.includes(4409), 15_000);
    await new Promise((resolve) => setTimeout(resolve, 3000));
    page = await content(owner.cookie, page.id);
    assert.equal(page.content_md, "# Markdown-Modus");
    assert.equal(page.collab_generation, patched.body.collab_generation);
    live.destroy();
    // A browser still holding the old generation is refused at the relay, with a close
    // code it can read.
    const stale = open(owner.cookie, page.id, 0);
    await until(() => stale.closes.includes(4409), 15_000);
    assert.ok(!stale.provider.synced);
    stale.destroy();

    // The next session starts from the new Markdown. Logging out is not a revocation
    // (review M2 R2): what was typed is saved, only that connection closes (4401), the
    // other browser goes on in the same generation.
    const second = await login("owner@it.example");
    const fresh = open(owner.cookie, page.id, page.collab_generation);
    const other = open(second.cookie, page.id, page.collab_generation);
    await Promise.all([synced(fresh), synced(other)]);
    assert.equal(yDocToMarkdown(fresh.doc), "# Markdown-Modus");
    type(fresh.doc, "Letzter Satz vor dem Abmelden");
    await until(() => yDocToMarkdown(other.doc).includes("Letzter Satz"));
    assert.equal(
      (await api("/api/auth/logout", { method: "POST", cookie: owner.cookie })).status,
      204,
    );
    await until(() => fresh.closes.includes(4401), 15_000);
    await until(
      async () => (await content(second.cookie, page.id)).content_md.includes("Letzter Satz"),
      15_000,
    );
    type(other.doc, " und weiter");
    await until(
      async () => (await content(second.cookie, page.id)).content_md.includes("und weiter"),
      15_000,
    );
    const after = await content(second.cookie, page.id);
    assert.equal(after.collab_generation, page.collab_generation);
    assert.deepEqual(other.closes, []);

    // The session cookie never reaches the collab process and opens nothing there
    // (plan M9 decision 16, R14): a valid login straight at its port is refused, and
    // the internal API takes the cookie's token for no grant.
    const direct = client(
      `ws://${collabBase}/collab/${page.id}?generation=${page.collab_generation}`,
      { cookie: second.cookie, origin: `http://${collabBase}`, name: `page:${page.id}` },
    );
    clients.push(direct);
    await until(() => direct.closes.includes(4401), 15_000);
    assert.ok(!direct.provider.synced);
    direct.destroy();
    const auth = await fetch(`${internalBase}/internal/collab/auth`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Herd-Internal-Token": INTERNAL_TOKEN },
      body: JSON.stringify({
        grant: second.cookie.split("=")[1],
        page_id: page.id,
        generation: page.collab_generation,
      }),
    });
    assert.equal(auth.status, 401);
    assert.equal((await auth.json()).error.code, "collab.grant_invalid");
  },
);
