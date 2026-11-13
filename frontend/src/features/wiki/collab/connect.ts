import { HocuspocusProvider, WebSocketStatus } from '@hocuspocus/provider'
import type * as Y from 'yjs'

// Stateless messages of the collab process (collab/live.mjs): the browser asks for an
// immediate save, the server answers whether everything is stored (review M2 R3).
export const FLUSH = 'herd:flush'
export const SAVED = 'herd:saved'
export const UNSAVED = 'herd:unsaved'
// The document's latest state cannot be stored as Markdown (nothing is stored until a
// later state can be), and that a later state was stored (review M2 S2/S3).
export const UNREPRESENTABLE = 'herd:unrepresentable'
export const REPRESENTABLE = 'herd:representable'
const FINISH_TIMEOUT_MS = 5000

export interface AwarenessState {
  clientId: number
  user?: { name?: unknown; color?: unknown }
}

export interface LiveHandlers {
  onClose: (code: number) => void
  onConnected: (connected: boolean) => void
  onSynced: () => void
  onUnsynced: (count: number) => void
  onPeers: (states: AwarenessState[]) => void
  /** True while the latest state cannot be saved as Markdown. */
  onUnrepresentable: (unrepresentable: boolean) => void
}

/** One live connection of a page's document. */
export interface LiveConnection {
  /** What the caret extension needs (it reads `awareness`); null without one. */
  provider: HocuspocusProvider | null
  clientId: number | null
  destroy: () => void
  /** "I am done": waits until the server has every local change and has stored it;
   *  false when it could not confirm that in time. Leaves the connection open. */
  finish?: () => Promise<boolean>
}

export type Connect = (options: {
  pageId: string
  generation: number
  doc: Y.Doc
  handlers: LiveHandlers
}) => LiveConnection

/** Same origin as the page: the session cookie goes along, the API relays. */
export function liveUrl(pageId: string, generation: number, location: Location = window.location) {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${location.host}/collab/${encodeURIComponent(pageId)}?generation=${generation}`
}

export const connectLive: Connect = ({ pageId, generation, doc, handlers }) => {
  const provider = new HocuspocusProvider({
    url: liveUrl(pageId, generation),
    name: `page:${pageId}`,
    document: doc,
    // Authentication is the session cookie; the protocol still wants a token message.
    token: 'session-cookie',
    onClose: ({ event }) => handlers.onClose(event.code),
    onStatus: ({ status }) => handlers.onConnected(status === WebSocketStatus.Connected),
    onSynced: ({ state }) => state && handlers.onSynced(),
    onUnsyncedChanges: ({ number }) => handlers.onUnsynced(number),
    onAwarenessChange: ({ states }) => handlers.onPeers(states as AwarenessState[]),
    onStateless: ({ payload }) => {
      if (payload === UNREPRESENTABLE || payload === REPRESENTABLE) {
        handlers.onUnrepresentable(payload === UNREPRESENTABLE)
      }
    },
  })
  return {
    provider,
    clientId: provider.awareness?.clientID ?? null,
    destroy: () => provider.destroy(),
    finish: () => finish(provider),
  }
}

function finish(provider: HocuspocusProvider): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    let asked = false
    const end = (saved: boolean) => {
      clearTimeout(timer)
      provider.off('unsyncedChanges', ask)
      provider.off('stateless', answer)
      resolve(saved)
    }
    const timer = setTimeout(() => end(false), FINISH_TIMEOUT_MS)
    const answer = ({ payload }: { payload: string }) => {
      if (payload === SAVED || payload === UNSAVED) end(payload === SAVED)
    }
    // Asked only once the server has every local change, so the save includes them.
    const ask = () => {
      if (asked || provider.hasUnsyncedChanges) return
      asked = true
      provider.on('stateless', answer)
      provider.sendStateless(FLUSH)
    }
    provider.on('unsyncedChanges', ask)
    ask()
  })
}
