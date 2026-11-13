import { expect, test } from 'vitest'
import { leaveReason, unsavedWork, type LeaveState } from './leaveRisk'

const untouched: LeaveState = {
  stopped: null,
  unsynced: 0,
  unrepresentable: false,
  unconfirmed: false,
  lostText: false,
}

test('the sync handshake of an untouched page is no unsaved work (review M4-1 P15)', () => {
  // The provider counts its own handshake as one unsynced change on every connect, until
  // the server answers ("Verbindet …", "Speichert …"): reloading then must not ask.
  expect(unsavedWork({ ...untouched, unsynced: 1 })).toBe(false)
  expect(unsavedWork(untouched)).toBe(false)
})

test('a change made here is unsaved work until the server confirms it stored', () => {
  expect(unsavedWork({ ...untouched, unconfirmed: true })).toBe(true)
  expect(leaveReason({ ...untouched, unconfirmed: true })).toBe('unconfirmed')
  // Not even sent yet (the connection is down): so worded.
  expect(leaveReason({ ...untouched, unconfirmed: true, unsynced: 2 })).toBe('unsent')
})

test('a state that cannot be saved, and text of an ended session, are unsaved work', () => {
  expect(unsavedWork({ ...untouched, unrepresentable: true })).toBe(true)
  expect(leaveReason({ ...untouched, unrepresentable: true })).toBe('unsaveable')
  expect(unsavedWork({ ...untouched, stopped: 'server_error', lostText: true })).toBe(true)
  expect(unsavedWork({ ...untouched, stopped: 'server_error', lostText: false })).toBe(false)
  expect(leaveReason({ ...untouched, stopped: 'server_error', lostText: true })).toBe('lost')
})
