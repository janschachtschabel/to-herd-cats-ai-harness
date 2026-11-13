import { useCallback, useEffect, useRef, useState } from 'react'
import * as Y from 'yjs'
import type { WikiPage } from '@/lib/api'
import { beforeLogout } from '@/lib/beforeLogout'
import { trackConfirmation } from './confirmation'
import { connectLive, type Connect, type LiveConnection } from './connect'
import { liveMarkdown } from './liveMarkdown'
import { closeOutcome, liveStatus, peersOf, type Peer, type StopReason } from './liveSession'

export interface LiveSession {
  doc: Y.Doc
  connection: LiveConnection | null
  generation: number
  status: ReturnType<typeof liveStatus>
  peers: Peer[]
  /** Not live any more (the editor turns read-only) and why. */
  stopped: StopReason | null
  /** A 4409 ended the previous generation; this is a fresh document. */
  regenerated: boolean
  /** The local document's Markdown when the connection ended for good or for a new
   *  generation, so text that may not have been saved can be copied. */
  lost: string | null
  unsynced: number
  /** The latest state cannot be saved as Markdown: the edits stay unsaved. */
  unrepresentable: boolean
  /** A change made here is not yet acknowledged as stored (review M2 T5). */
  unconfirmed: boolean
  retry: () => void
  /** Stop for good on the browser's side (the shared document cannot be shown). */
  refuse: (reason: StopReason) => void
  /** The editor changed the document it had just loaded (review M2 ruling B): report
   *  it and stop for good, as for content the editor cannot show. */
  loadMutation: () => void
  /** "Fertig": true once the server has stored everything typed here (or nothing more
   *  can be stored because the session ended); false while that is not confirmed. */
  finish: () => Promise<boolean>
}

/**
 * The page's live document: one Y.Doc and connection per generation. Close codes
 * (see liveSession.ts): 4409 → the connection ends, the page is fetched again and a
 * new connection with a fresh document joins the new generation; 4401/4403/4404/4413
 * (and 4400/4503) → stop reconnecting, keep the text read-only; anything else → the
 * provider reconnects by itself.
 */
export function useLiveSession(
  page: WikiPage,
  refetch: () => Promise<WikiPage>,
  connect: Connect = connectLive,
): LiveSession {
  const generation = page.collab_generation
  const [doc, setDoc] = useState(() => new Y.Doc())
  const [connection, setConnection] = useState<LiveConnection | null>(null)
  const [connected, setConnected] = useState(false)
  const [synced, setSynced] = useState(false)
  const [unsynced, setUnsynced] = useState(0)
  const [unrepresentable, setUnrepresentable] = useState(false)
  const [unconfirmed, setUnconfirmed] = useState(false)
  const [peers, setPeers] = useState<Peer[]>([])
  const [stopped, setStopped] = useState<StopReason | null>(null)
  const [regenerated, setRegenerated] = useState(false)
  const [lost, setLost] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const ended = useRef<number | null>(null) // the generation a 4409 ended
  const current = useRef<{
    live: LiveConnection
    open: () => boolean
    stop: (reason: StopReason) => void
    unconfirmed: () => boolean
  } | null>(null)
  const refetchRef = useRef(refetch)
  useEffect(() => {
    refetchRef.current = refetch
  })

  useEffect(() => {
    if (ended.current !== null && ended.current >= generation) return // waiting for the refetch
    const fresh = new Y.Doc()
    let open = true
    const confirmation = trackConfirmation(fresh, (value) => open && setUnconfirmed(value))
    const live = connect({
      pageId: page.id,
      generation,
      doc: fresh,
      handlers: {
        onConnected: (value) => open && setConnected(value),
        onSynced: () => open && setSynced(true),
        onUnsynced: (count) => open && setUnsynced(count),
        onPeers: (states) => open && setPeers(peersOf(states, live.clientId)),
        onUnrepresentable: (value) => open && setUnrepresentable(value),
        onStored: (snapshot) => open && confirmation.stored(snapshot),
        onClose: (code) => {
          if (!open) return
          const outcome = closeOutcome(code)
          if (outcome.kind === 'retry') return
          end()
          queueMicrotask(() => live.destroy())
          if (outcome.kind === 'stop') {
            setStopped(outcome.reason)
            return
          }
          ended.current = generation
          refetchRef.current().then(
            (latest) => {
              if (latest.collab_generation > generation) setRegenerated(true)
              else setStopped('invalid')
            },
            () => setStopped('not_found'),
          )
        },
      },
    })
    function end() {
      open = false
      let text: string | null = null
      try {
        text = liveMarkdown(fresh)
      } catch {
        // content the schema does not allow: nothing to copy
      }
      setLost(text)
      setConnected(false)
      setPeers([])
    }
    const stop = (reason: StopReason) => {
      if (!open) return
      live.destroy() // at once: nothing more may reach the server
      end()
      setStopped(reason)
    }
    current.current = { live, open: () => open, stop, unconfirmed: confirmation.unconfirmed }
    const unregister = beforeLogout(async () => {
      if (open) await live.finish?.()
      open = false
      live.destroy()
    })
    setDoc(fresh)
    setConnection(live)
    setSynced(false)
    setUnsynced(0)
    setUnrepresentable(false)
    setUnconfirmed(false)
    setStopped(null)
    return () => {
      open = false
      current.current = null
      confirmation.destroy()
      unregister()
      live.destroy()
      fresh.destroy()
    }
  }, [connect, page.id, generation, attempt])

  const retry = useCallback(() => {
    ended.current = null
    setLost(null)
    setRegenerated(false)
    setAttempt((n) => n + 1)
  }, [])

  const refuse = useCallback((reason: StopReason) => current.current?.stop(reason), [])

  const loadMutation = useCallback(() => {
    const session = current.current
    if (!session || !session.open()) return
    session.live.reportLoadMutation?.()
    session.stop('invalid_content')
  }, [])

  const finish = useCallback(async () => {
    const session = current.current
    if (!session || !session.open() || !session.live.finish) return true
    // Stored, and the acknowledgement holds every change made here.
    return (await session.live.finish()) && !session.unconfirmed()
  }, [])

  return {
    doc,
    connection,
    generation,
    status: liveStatus({ connected, synced, unsynced }),
    peers,
    stopped,
    regenerated,
    lost,
    unsynced,
    unrepresentable,
    unconfirmed,
    retry,
    refuse,
    loadMutation,
    finish,
  }
}
