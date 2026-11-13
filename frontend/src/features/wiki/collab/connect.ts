import { HocuspocusProvider, WebSocketStatus } from '@hocuspocus/provider'
import type * as Y from 'yjs'

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
}

/** One live connection of a page's document. */
export interface LiveConnection {
  /** What the caret extension needs (it reads `awareness`); null without one. */
  provider: HocuspocusProvider | null
  clientId: number | null
  destroy: () => void
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
  })
  return {
    provider,
    clientId: provider.awareness?.clientID ?? null,
    destroy: () => provider.destroy(),
  }
}
