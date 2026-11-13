/** How the browser reacts to the close codes of `/collab/<page>` (relay and collab
 *  process; README "Live-Bearbeitung"). */
export type StopReason =
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'too_large'
  | 'not_roundtrip_safe'
  | 'invalid_content'
  | 'connection_limit'
  | 'off'
  | 'invalid'
  | 'server_error'

/** Stops after which reconnecting cannot help, so no "reload" is offered. */
export const FINAL_STOPS: ReadonlySet<StopReason> = new Set([
  'unauthorized',
  'not_roundtrip_safe',
  'invalid_content',
])

/** Stops after which the page can still be edited in the Markdown editor. */
export const MARKDOWN_STOPS: ReadonlySet<StopReason> = new Set([
  'not_roundtrip_safe',
  'too_large',
  'invalid_content',
  'server_error',
])

/** A server error (1011: the collab process or the relay failed on this page) this
 *  often in a row without getting in stops (review M2 U3): retrying could not help, and
 *  the editor said "Verbindet …" for ever. */
export const SERVER_ERROR_ATTEMPTS = 3

export type CloseOutcome =
  /** The generation ended (a change outside the live session): fetch the page and
   *  join its new generation with a fresh document. */
  | { kind: 'regenerate' }
  /** Reconnecting cannot help: stop and say why. */
  | { kind: 'stop'; reason: StopReason }
  /** Restarting, busy or briefly unreachable: the provider reconnects on its own. */
  | { kind: 'retry' }

const STOPS: Record<number, StopReason> = {
  4400: 'invalid',
  4401: 'unauthorized',
  4403: 'forbidden',
  4404: 'not_found',
  4413: 'too_large',
  4422: 'not_roundtrip_safe',
  4429: 'connection_limit',
  4503: 'off',
}

/** What a close means; `serverErrors`: the 1011 closes before this one since the
 *  connection last got in. */
export function closeOutcome(code: number, serverErrors = 0): CloseOutcome {
  if (code === 4409) return { kind: 'regenerate' }
  if (code === 1011 && serverErrors + 1 >= SERVER_ERROR_ATTEMPTS) {
    return { kind: 'stop', reason: 'server_error' }
  }
  const reason = STOPS[code]
  return reason ? { kind: 'stop', reason } : { kind: 'retry' }
}

/** What the status line says. */
export type LiveStatus = 'connecting' | 'synced' | 'saving' | 'offline'

export function liveStatus(state: {
  connected: boolean
  synced: boolean
  unsynced: number
}): LiveStatus {
  if (!state.connected) return state.synced ? 'offline' : 'connecting'
  if (!state.synced) return 'connecting'
  return state.unsynced > 0 ? 'saving' : 'synced'
}

/** Someone else in the document, as the collab process names them (verified name and
 *  a colour per person; the server overwrites what a browser claims). */
export interface Peer {
  clientId: number
  name: string
  color: string
}

export function peersOf(
  states: { clientId: number; user?: { name?: unknown; color?: unknown } }[],
  ownClientId: number | null,
): Peer[] {
  return states.flatMap((state) => {
    const { name, color } = state.user ?? {}
    if (state.clientId === ownClientId || typeof name !== 'string') return []
    return [
      { clientId: state.clientId, name, color: typeof color === 'string' ? color : '#64748b' },
    ]
  })
}
