import { describe, expect, test } from 'vitest'
import * as Y from 'yjs'
import { trackConfirmation } from './confirmation'

/** What the collab process acknowledges after a save: a snapshot of what it stored. */
function storedAs(server: Y.Doc) {
  return Y.encodeSnapshot(Y.snapshot(server))
}

function setup() {
  const doc = new Y.Doc()
  const server = new Y.Doc()
  const seen: boolean[] = []
  const tracker = trackConfirmation(doc, (unconfirmed) => seen.push(unconfirmed))
  // The browser's updates reach the server (as the provider sends them).
  doc.on('update', (update: Uint8Array, origin: unknown) => {
    if (origin !== 'server') Y.applyUpdate(server, update, 'browser')
  })
  return { doc, server, tracker, seen, text: doc.getText('t') }
}

describe('whether this browser’s changes are stored (review M2 T5)', () => {
  test('nothing typed: confirmed', () => {
    const { tracker } = setup()
    expect(tracker.unconfirmed()).toBe(false)
  })

  test('typed: unconfirmed until a save that holds it is acknowledged', () => {
    const { doc, server, tracker, seen, text } = setup()
    const before = storedAs(server)
    text.insert(0, 'abc')
    expect(tracker.unconfirmed()).toBe(true)
    tracker.stored(before) // an older save
    expect(tracker.unconfirmed()).toBe(true)
    tracker.stored(storedAs(server))
    expect(tracker.unconfirmed()).toBe(false)
    expect(seen).toEqual([true, false])
    expect(doc.clientID).toBeGreaterThan(0)
  })

  test('a deletion alone is unconfirmed until the save holds it', () => {
    const { server, tracker, text } = setup()
    text.insert(0, 'abc')
    tracker.stored(storedAs(server))
    const saved = storedAs(server)
    text.delete(0, 1)
    expect(tracker.unconfirmed()).toBe(true)
    tracker.stored(saved)
    expect(tracker.unconfirmed()).toBe(true)
    tracker.stored(storedAs(server))
    expect(tracker.unconfirmed()).toBe(false)
  })

  test("other people's changes do not count", () => {
    const { doc, tracker } = setup()
    const other = new Y.Doc()
    other.getText('t').insert(0, 'fremd')
    Y.applyUpdate(doc, Y.encodeStateAsUpdate(other), 'server')
    expect(tracker.unconfirmed()).toBe(false)
  })
})
