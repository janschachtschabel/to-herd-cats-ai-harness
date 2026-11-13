import type { StopReason } from './liveSession'

/** What leaving the live editor could lose (review M2 T5, U9; M4-1 P15). */
export interface LeaveState {
  stopped: StopReason | null
  /** The provider's count of changes the server has not answered yet. It counts its own
   *  sync handshake as one on every connect, so it says nothing about the person's work. */
  unsynced: number
  /** The latest state cannot be saved as Markdown. */
  unrepresentable: boolean
  /** A change made here is not acknowledged as stored (own insertions and deletions). */
  unconfirmed: boolean
  /** Once stopped: the text that may not have been saved differs from the page and has
   *  not been copied. */
  lostText: boolean
}

/** Whether leaving now could lose something: only a change made here that is not stored
 *  (or a state that cannot be), never the handshake of an untouched page. */
export function unsavedWork(state: LeaveState): boolean {
  if (state.stopped !== null) return state.lostText
  return state.unrepresentable || state.unconfirmed
}

export type LeaveReason = 'lost' | 'unsaveable' | 'unsent' | 'unconfirmed'

/** Why leaving asks (the question's wording, `wiki.live.leaveConfirm.*`). */
export function leaveReason(state: LeaveState): LeaveReason {
  if (state.stopped !== null) return 'lost'
  if (state.unrepresentable) return 'unsaveable'
  if (state.unsynced > 0) return 'unsent'
  return 'unconfirmed'
}
