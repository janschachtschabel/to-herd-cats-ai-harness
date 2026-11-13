import { describe, expect, test } from 'vitest'
import { closeOutcome, liveStatus, peersOf } from './liveSession'

describe('live session', () => {
  test('close codes', () => {
    expect(closeOutcome(4409)).toEqual({ kind: 'regenerate' })
    expect(closeOutcome(4401)).toEqual({ kind: 'stop', reason: 'unauthorized' })
    expect(closeOutcome(4403)).toEqual({ kind: 'stop', reason: 'forbidden' })
    expect(closeOutcome(4404)).toEqual({ kind: 'stop', reason: 'not_found' })
    expect(closeOutcome(4413)).toEqual({ kind: 'stop', reason: 'too_large' })
    expect(closeOutcome(4422)).toEqual({ kind: 'stop', reason: 'not_roundtrip_safe' })
    expect(closeOutcome(4429)).toEqual({ kind: 'stop', reason: 'connection_limit' })
    expect(closeOutcome(4503)).toEqual({ kind: 'stop', reason: 'off' })
    for (const code of [1000, 1006, 1012, 1013, 4408, 4502, 4504]) {
      expect(closeOutcome(code)).toEqual({ kind: 'retry' })
    }
  })

  test('status', () => {
    expect(liveStatus({ connected: false, synced: false, unsynced: 0 })).toBe('connecting')
    expect(liveStatus({ connected: true, synced: false, unsynced: 0 })).toBe('connecting')
    expect(liveStatus({ connected: true, synced: true, unsynced: 0 })).toBe('synced')
    expect(liveStatus({ connected: true, synced: true, unsynced: 2 })).toBe('saving')
    expect(liveStatus({ connected: false, synced: true, unsynced: 0 })).toBe('offline')
  })

  test('peers leave out oneself and nameless states', () => {
    const states = [
      { clientId: 1, user: { name: 'Ich', color: '#111111' } },
      { clientId: 2, user: { name: 'Lea', color: '#222222' } },
      { clientId: 3 },
    ]
    expect(peersOf(states, 1)).toEqual([{ clientId: 2, name: 'Lea', color: '#222222' }])
  })
})
