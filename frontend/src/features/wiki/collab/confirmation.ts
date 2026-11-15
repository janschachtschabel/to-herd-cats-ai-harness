import * as Y from 'yjs'

type DeleteSet = Y.Transaction['deleteSet']

export interface Confirmation {
  /** True while a change made in this browser is not known to be stored. */
  unconfirmed: () => boolean
  /** The collab process stored this snapshot (`herd:stored:`, collab/protocol.mjs). */
  stored: (snapshot: Uint8Array) => void
  destroy: () => void
}

/** Whether every change made in this browser is in a state the collab process has
 *  acknowledged as stored (review M2 T5): its own insertions (its clock in the stored
 *  state vector) and its own deletions (in the stored deletions). A state the server
 *  refuses is never acknowledged, so its changes stay unconfirmed. */
export function trackConfirmation(
  doc: Y.Doc,
  onChange: (unconfirmed: boolean) => void,
): Confirmation {
  let stored: Y.Snapshot | null = null
  let deletions: DeleteSet[] = [] // own deletions not yet seen stored
  let current = false

  const held = (deleteSet: DeleteSet) => {
    if (!stored) return false
    for (const [client, items] of deleteSet.clients) {
      for (const { clock, len } of items) {
        for (let at = clock; at < clock + len; at++) {
          if (!Y.isDeleted(stored.ds, new Y.ID(client, at))) return false
        }
      }
    }
    return true
  }
  const unconfirmed = () => {
    const own = Y.getState(doc.store, doc.clientID)
    if (own > (stored?.sv.get(doc.clientID) ?? 0)) return true
    deletions = deletions.filter((deleteSet) => !held(deleteSet))
    return deletions.length > 0
  }
  const update = () => {
    const next = unconfirmed()
    if (next !== current) {
      current = next
      onChange(next)
    }
  }
  const observe = (transaction: Y.Transaction) => {
    if (!transaction.local) return
    if (transaction.deleteSet.clients.size > 0) deletions.push(transaction.deleteSet)
    update()
  }
  doc.on('afterTransaction', observe)
  return {
    unconfirmed,
    stored: (snapshot) => {
      stored = Y.decodeSnapshot(snapshot)
      update()
    },
    destroy: () => doc.off('afterTransaction', observe),
  }
}
