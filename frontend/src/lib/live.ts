import { useEffect, useRef, useSyncExternalStore } from 'react'

/** The events of `GET /api/stream`. Each carries ids only, never content: whoever
 *  listens refetches through the API (the server checked the rights for the ids). */
export const LIVE_EVENTS = [
  'message.created',
  'message.updated',
  'message.deleted',
  'reaction.changed',
  'notification.created',
  'conversation.read',
  'channel.changed',
  'activity.changed',
  'access.changed',
  'dm.inspected',
  'ticket.created',
  'ticket.updated',
  'sprint.changed',
  'run.progress',
  'proposal.changed',
  'card.changed',
  'skill_proposal.changed',
  'automation.changed',
  'backup.changed',
  'calendar.changed',
  'resync',
] as const

export type LiveEventType = (typeof LIVE_EVENTS)[number]

export interface LiveEvent {
  type: LiveEventType
  conversationId: string | null
  messageId: string | null
  parentId: string | null
  /** The ticket of `ticket.created` / `ticket.updated` (its thread is `conversationId`). */
  ticketId: string | null
  /** The ticket's space (ticket events), the sprint's (`sprint.changed`). */
  spaceId: string | null
  /** An agent's run and its step counter (`run.progress` only). */
  runId?: string | null
  step?: number | null
  /** A page proposal (`proposal.changed`, with its space) or a skill proposal
   *  (`skill_proposal.changed`). */
  proposalId?: string | null
  /** An automation that changed or fired a term (`automation.changed`, with the space
   *  of its place; none for a DM). */
  automationId?: string | null
  /** A calendar whose events changed (`calendar.changed`, with its space). */
  calendarId?: string | null
}

/** `limited`: the server refused another stream for this session (429, too many tabs). */
export type LiveStatus = 'connecting' | 'open' | 'retrying' | 'limited'

/** Waits before opening again after the server refused or closed the stream. */
export const BACKOFF_MS = [5_000, 10_000, 30_000, 60_000] as const

const RESYNC: LiveEvent = {
  type: 'resync',
  conversationId: null,
  messageId: null,
  parentId: null,
  ticketId: null,
  spaceId: null,
}

let status: LiveStatus = 'connecting'
const listeners = new Set<() => void>()

function setStatus(next: LiveStatus): void {
  if (next === status) return
  status = next
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The state of this tab's stream, for a quiet hint while it is not open. */
export function useLiveStatus(): LiveStatus {
  return useSyncExternalStore(subscribe, () => status)
}

function idOrNull(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/** An event's data (`{"conversation_id", "message_id", "parent_id"}`, tickets add
 *  `ticket_id` and `space_id`; a sprint's is `{"space_id", "sprint_id"}`, and the
 *  space is all a client refreshes by; an agent run's progress adds `run_id` and
 *  `step`; a proposal's is `{"space_id", "proposal_id"}`, a skill proposal's adds
 *  `proposal_id`; an automation's is `{"automation_id", "space_id"}`; a calendar's
 *  `{"space_id", "calendar_id"}`); null if unreadable. */
export function parseLiveEvent(type: LiveEventType, data: string): LiveEvent | null {
  try {
    const value: unknown = JSON.parse(data || '{}')
    if (typeof value !== 'object' || value === null) return null
    const fields = value as Record<string, unknown>
    const event: LiveEvent = {
      type,
      conversationId: idOrNull(fields.conversation_id),
      messageId: idOrNull(fields.message_id),
      parentId: idOrNull(fields.parent_id),
      ticketId: idOrNull(fields.ticket_id),
      spaceId: idOrNull(fields.space_id),
    }
    if (type === 'proposal.changed' || type === 'skill_proposal.changed') {
      return { ...event, proposalId: idOrNull(fields.proposal_id) }
    }
    if (type === 'automation.changed') {
      return { ...event, automationId: idOrNull(fields.automation_id) }
    }
    if (type === 'calendar.changed') {
      return { ...event, calendarId: idOrNull(fields.calendar_id) }
    }
    if (type !== 'run.progress') return event
    const step = Number.isInteger(fields.step) ? (fields.step as number) : null
    return { ...event, runId: idOrNull(fields.run_id), step }
  } catch {
    return null
  }
}

/** Whether the server refuses the stream because this session has too many (429).
 *  EventSource cannot tell; a plain request can, and is dropped after its headers. */
async function refusedForLimit(url: string): Promise<boolean> {
  const controller = new AbortController()
  try {
    const response = await globalThis.fetch(url, {
      credentials: 'include',
      signal: controller.signal,
    })
    return response.status === 429
  } catch {
    return false
  } finally {
    controller.abort()
  }
}

/**
 * Keeps this tab's one stream open while mounted (mount it once, in the shell). The
 * browser reconnects by itself after a dropped connection; when the server refuses
 * (401, 429, 503) the stream is opened again after a growing wait. Nothing missed is
 * replayed: after any interruption `onEvent` gets a `resync`, as for the server's own.
 */
export function useLive(onEvent: (event: LiveEvent) => void, url = '/api/stream'): void {
  const handler = useRef(onEvent)
  useEffect(() => {
    handler.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    let source: EventSource | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    let interrupted = false
    let stopped = false

    const connect = () => {
      setStatus(failures > 0 ? 'retrying' : 'connecting')
      const current = new EventSource(url, { withCredentials: true })
      source = current
      current.onopen = () => {
        if (interrupted) handler.current(RESYNC)
        interrupted = false
        failures = 0
        setStatus('open')
      }
      current.onerror = () => {
        interrupted = true
        if (current.readyState !== EventSource.CLOSED) {
          setStatus('retrying') // the browser tries again on its own
          return
        }
        current.close()
        const wait = BACKOFF_MS[Math.min(failures, BACKOFF_MS.length - 1)]
        failures += 1
        setStatus('retrying')
        void refusedForLimit(url).then((limited) => {
          if (!stopped && limited) setStatus('limited')
        })
        timer = setTimeout(connect, wait)
      }
      for (const type of LIVE_EVENTS) {
        current.addEventListener(type, (event) => {
          const parsed = parseLiveEvent(type, (event as MessageEvent<string>).data)
          if (parsed) handler.current(parsed)
        })
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      source?.close()
      setStatus('connecting')
    }
  }, [url])
}
