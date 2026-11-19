// End to end with two collab instances (plan M9 task 15, decision 17): the real API
// (`integration-backend.mjs`) and two collab processes of their own (role collab); the
// one of role all is set draining first, so that only these two take pages. Two
// browsers of one page land on the same instance; stopping it (SIGTERM: it drains) moves
// them to the other without losing what was saved, or typed just before the stop.
// Runs only with HERD_COLLAB_INTEGRATION=1 (`npm run test:integration`).
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { yDocToMarkdown } from "../markdown.mjs";
import { synced, type, until } from "./helpers.mjs";
import { enabled, startBackend } from "./integration-backend.mjs";

let it;

before(async () => {
  if (!enabled) return;
  it = await startBackend();
});

after(async () => {
  if (enabled) await it?.stop();
});

test(
  "two browsers of a page share one instance and move together when it stops",
  { skip: !enabled, timeout: 180_000 },
  async () => {
    const { api, psql } = it;
    // Only the two instances below take new pages.
    psql("UPDATE collab_instance SET draining = true");
    const instances = [await it.spawnCollab(), await it.spawnCollab()];
    await until(
      () => psql("SELECT count(*) FROM collab_instance WHERE NOT draining") === "2",
      15_000,
    );
    const first = await it.login("owner@it.example");
    const second = await it.login("owner@it.example");
    const space = (
      await api("/api/spaces", {
        method: "POST",
        cookie: first.cookie,
        body: { name: "Zwei", kind: "team" },
      })
    ).body;
    let page = (
      await api(`/api/spaces/${space.id}/pages`, {
        method: "POST",
        cookie: first.cookie,
        body: { title: "Zwei Instanzen", content_md: "# Start" },
      })
    ).body;
    page = (
      await api(`/api/pages/${page.id}/publish`, {
        method: "POST",
        cookie: first.cookie,
        body: { version: page.version },
      })
    ).body;
    const owner = () =>
      psql(
        "SELECT i.url || ' ' || o.epoch FROM collab_page_owner o" +
          ` JOIN collab_instance i ON i.id = o.instance_id WHERE o.page_id = '${page.id}'`,
      );

    // Both browsers land on the instance that owns the page.
    const a = it.open(first.cookie, page.id, 0);
    const b = it.open(second.cookie, page.id, 0);
    await Promise.all([synced(a), synced(b)]);
    const counts = await Promise.all(instances.map((i) => i.documents()));
    assert.deepEqual([...counts].sort(), [0, 1]);
    const holder = instances[counts.indexOf(1)];
    const other = instances[counts.indexOf(0)];
    assert.equal(owner(), `${holder.url} 1`);
    type(a.doc, "Gespeichert");
    await until(() => yDocToMarkdown(b.doc).includes("Gespeichert"));
    const saved = "# Start\n\nGespeichert";
    await until(async () => (await it.content(first.cookie, page.id)).content_md === saved, 15_000);

    // Typed right before the instance stops: it drains, so this is saved too.
    type(b.doc, " und kurz vor dem Stopp");
    await until(() => yDocToMarkdown(a.doc).includes("kurz vor dem Stopp")); // it has it
    await holder.stop();
    const stopped = `${saved} und kurz vor dem Stopp`;
    assert.equal((await it.content(first.cookie, page.id)).content_md, stopped);

    // The browsers reconnect by themselves, through the relay, to the other instance.
    await until(() => owner() === `${other.url} 2`, 30_000);
    await until(async () => (await other.documents()) === 1, 30_000);
    assert.ok(a.closes.includes(1012) && b.closes.includes(1012), JSON.stringify(a.closes));
    type(a.doc, " und danach");
    await until(() => yDocToMarkdown(b.doc).includes("und danach"), 15_000);
    await until(
      async () => (await it.content(first.cookie, page.id)).content_md === `${stopped} und danach`,
      15_000,
    );
    page = await it.content(first.cookie, page.id);
    assert.equal(page.collab_generation, 0, "the instance changed, the generation did not");
    assert.ok(!a.closes.includes(4409) && !b.closes.includes(4409), JSON.stringify(a.closes));
  },
);
