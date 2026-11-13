// Who is in a document, as the server says (review M2 R12). Each connection owns one
// awareness client id: the first it sends that no other connection owns. Entries for
// any other id, and removals of them, are dropped from its updates; its own entry
// keeps only the cursor and gets the authenticated person's name and colour.
import { colorFor } from "./protocol.mjs";

const CLIENT_FIELDS = ["cursor"]; // what a browser may set itself (the caret)

export function presenceGuard() {
  const owners = new Map(); // document name -> Map(client id -> socket id)
  const owned = new Map(); // socket id -> [document name, client id]

  function owner(documentName, socketId, clientId) {
    let clients = owners.get(documentName);
    if (!clients) owners.set(documentName, (clients = new Map()));
    if (!clients.has(clientId) && !owned.has(socketId)) {
      clients.set(clientId, socketId);
      owned.set(socketId, [documentName, clientId]);
    }
    return clients.get(clientId);
  }

  return {
    /** Rewrites an awareness update of one connection in place. */
    filter({ context, documentName, socketId, states, removedClients }) {
      for (const clientId of [...states.keys()]) {
        if (!context?.user || owner(documentName, socketId, clientId) !== socketId) {
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

    /** A connection left: its client id is free again. */
    forget(socketId) {
      const entry = owned.get(socketId);
      if (!entry) return;
      owned.delete(socketId);
      const clients = owners.get(entry[0]);
      clients?.delete(entry[1]);
      if (clients?.size === 0) owners.delete(entry[0]);
    },
  };
}
