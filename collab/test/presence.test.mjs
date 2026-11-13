// Presence is the server's (review M2 R12): each connection's entry carries the
// authenticated person's name and colour and nothing a client may not set; a
// connection cannot write another connection's entry.
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import * as encoding from "lib0/encoding";
import { Awareness, encodeAwarenessUpdate } from "y-protocols/awareness";
import * as Y from "yjs";
import { colorFor } from "../protocol.mjs";
import { createCollabServer } from "../server.mjs";
import { PAGE, liveFixture, synced, until } from "./helpers.mjs";

let live;

afterEach(async () => {
  await live?.stop();
  live = null;
});

/** An awareness update for `clientId` sent raw over `sender`'s socket. */
function sendAs(sender, clientId, state) {
  const forged = new Awareness(new Y.Doc());
  forged.states.set(clientId, state);
  forged.meta.set(clientId, { clock: 99_999, lastUpdated: Date.now() });
  const encoder = encoding.createEncoder();
  encoding.writeVarString(encoder, `page:${PAGE}`);
  encoding.writeVarUint(encoder, 1); // awareness
  encoding.writeVarUint8Array(encoder, encodeAwarenessUpdate(forged, [clientId]));
  sender.provider.configuration.websocketProvider.send(encoding.toUint8Array(encoder));
  forged.destroy(); // its timer would keep the process alive
}

const seen = (viewer, clientId) => viewer.provider.awareness.getStates().get(clientId);

test("each entry is the authenticated person's; another's cannot be written", async () => {
  live = await liveFixture({ createCollabServer });
  const anna = live.open({ cookie: "herd_session=token-a" });
  const ben = live.open({ cookie: "herd_session=token-b" });
  const third = live.open({ cookie: "herd_session=token-a" });
  await Promise.all([anna, ben, third].map(synced));
  anna.provider.setAwarenessField("cursor", null);
  ben.provider.setAwarenessField("user", { name: "Geschäftsführung", id: "x", admin: true });
  ben.provider.setAwarenessField("admin", true);
  const annaId = anna.doc.clientID;
  const benId = ben.doc.clientID;
  await until(() => seen(third, annaId)?.user && seen(third, benId)?.user);
  assert.deepEqual(seen(third, benId).user, { name: "Ben", color: colorFor("user-b") });
  assert.equal(seen(third, benId).admin, undefined, "fields a client may not set are dropped");
  // Ben writes an entry for Anna's client id: dropped.
  sendAs(ben, annaId, { user: { name: "FAKE" }, cursor: null });
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.deepEqual(seen(third, annaId).user, { name: "Anna", color: colorFor("user-a") });
  // Nor can he remove it.
  sendAs(ben, annaId, null);
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.ok(seen(third, annaId), "Anna is still present");
});
