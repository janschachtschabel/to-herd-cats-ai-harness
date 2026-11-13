// Who is in a document, as the server says (review M2 R12). Each connection owns one
// awareness client id: the first it sends that no other connection owns. Entries for
// any other id, and removals of them, are dropped from its updates; its own entry
// keeps only the cursor and gets the authenticated person's name and colour. When a
// connection closes, its id stays its person's for a while (the browser reconnects
// with the same id): nobody else can take it over in the meantime (review M2 S12).
import { colorFor } from "./protocol.mjs";

const CLIENT_FIELDS = ["cursor"]; // what a browser may set itself (the caret)

const KEPT_MS = 10 * 60_000; // how long a closed connection's id stays its person's

export function presenceGuard({ keptMs = KEPT_MS } = {}) {
  const owners = new Map(); // document name -> Map(client id -> socket id)
  const owned = new Map(); // socket id -> [document name, client id, user id]
  const kept = new Map(); // `${document name} ${client id}` -> { userId, until }

  function owner(documentName, socketId, clientId, userId) {
    let clients = owners.get(documentName);
    if (!clients) owners.set(documentName, (clients = new Map()));
    if (!clients.has(clientId) && !owned.has(socketId)) {
      const key = `${documentName} ${clientId}`;
      const left = kept.get(key);
      if (left && left.until > Date.now() && left.userId !== userId) return undefined;
      kept.delete(key);
      clients.set(clientId, socketId);
      owned.set(socketId, [documentName, clientId, userId]);
    }
    return clients.get(clientId);
  }

  return {
    /** Rewrites an awareness update of one connection in place. */
    filter({ context, documentName, socketId, states, removedClients }) {
      for (const clientId of [...states.keys()]) {
        if (
          !context?.user ||
          owner(documentName, socketId, clientId, context.user.id) !== socketId
        ) {
          states.delete(clientId);
          continue;
        }
        const sent = states.get(clientId) ?? {};
        const kept = Object.fromEntries(
          CLIENT_FIELDS.filter((f) => f in sent).map((f) => [f, sent[f]]),
        );
        kept.user = { name: context.user.name, color: colorFor(context.user.id) };
        states.set(clientId, kept);
      }
      for (const clientId of [...removedClients]) {
        if (owners.get(documentName)?.get(clientId) !== socketId) removedClients.delete(clientId);
      }
    },

    /** A connection left: its client id is free again, for its person first. */
    forget(socketId) {
      const entry = owned.get(socketId);
      if (!entry) return;
      const [documentName, clientId, userId] = entry;
      owned.delete(socketId);
      const clients = owners.get(documentName);
      clients?.delete(clientId);
      if (clients?.size === 0) owners.delete(documentName);
      const now = Date.now();
      for (const [key, left] of kept) if (left.until <= now) kept.delete(key);
      kept.set(`${documentName} ${clientId}`, { userId, until: now + keptMs });
    },
  };
}
