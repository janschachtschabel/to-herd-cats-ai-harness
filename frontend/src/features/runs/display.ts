import type { TFunction } from 'i18next'
import type { Run } from '@/features/agents/queries'
import { hasPermission } from '@/features/auth/queries'
import type { Me } from '@/lib/api'
import { ticketKey } from '@/features/tickets/refs'
import type { RunState } from './queries'
import { externalToolName } from './timeline'

export const RUN_STATES: readonly RunState[] = ['queued', 'running', 'waiting', 'done']

/** A run's state in words; a finished one by how it ended. */
export function stateText(t: TFunction, run: Pick<Run, 'state' | 'stop_reason'>): string {
  if (run.state !== 'done') return t(`runs.states.${run.state}`)
  return run.stop_reason === 'completed' ? t('runs.states.completed') : t('runs.states.stopped')
}

/** The tone of a run's state badge (the words beside it carry the meaning). */
export function stateTone(run: Pick<Run, 'state' | 'stop_reason'>): 'active' | 'ok' | 'stopped' {
  if (run.state !== 'done') return 'active'
  return run.stop_reason === 'completed' ? 'ok' : 'stopped'
}

/** How long the run has taken (so far): from its start, or its creation while queued. */
export function durationMs(run: Run, now: number): number {
  const from = Date.parse(run.started_at ?? run.created_at)
  const to = run.finished_at ? Date.parse(run.finished_at) : now
  return Math.max(0, to - from)
}

/** A duration in words: "850 ms", "12 s", "3 min 5 s", "2 h 4 min". */
export function formatDuration(t: TFunction, ms: number): string {
  if (ms < 1000) return t('runs.duration.ms', { count: Math.round(ms) })
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return t('runs.duration.s', { count: seconds })
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('runs.duration.min', { minutes, seconds: seconds % 60 })
  return t('runs.duration.h', { hours: Math.floor(minutes / 60), minutes: minutes % 60 })
}

/** Where a run answers, in words: the ticket's key, or the kind of place. */
export function placeText(t: TFunction, run: Run): string {
  const place = run.place
  if (place.kind === 'thread_ticket' && place.ticket_number) return ticketKey(place.ticket_number)
  return t(`runs.places.${place.kind}`)
}

/** Where a link to a run's place leads, if the reader may follow it: a ticket or page
 *  the API named (it names them only to readers of the space), a channel in a space the
 *  reader reads, the direct message only for the person who asked (who is in it). */
export type PlaceLink =
  | { to: 'ticket'; number: number }
  | { to: 'page'; pageId: string }
  | { to: 'conversation'; conversationId: string }

export function placeLink(run: Run, meId: string | undefined): PlaceLink | null {
  const place = run.place
  if (place.kind === 'thread_ticket') {
    return place.ticket_number ? { to: 'ticket', number: place.ticket_number } : null
  }
  if (place.kind === 'thread_page')
    return place.page_id ? { to: 'page', pageId: place.page_id } : null
  if (place.kind === 'channel') {
    return place.space_id ? { to: 'conversation', conversationId: place.conversation_id } : null
  }
  return meId !== undefined && run.asker_id === meId
    ? { to: 'conversation', conversationId: place.conversation_id }
    : null
}

/** Whether a stop can still be asked for: the run is not finished and nobody asked yet
 *  (whoever sees a run may stop it; the API answers 409 `run.finished` otherwise). */
export function mayCancel(run: Run): boolean {
  return run.state !== 'done' && !run.cancel_requested
}

/** A tool's name in words (unknown tools by their name; an external server's tool by
 *  its own name, marked as external). */
export function toolText(t: TFunction, name: string): string {
  const external = externalToolName(name)
  if (external) return t('runs.external.named', { name: external })
  return t(`agents.tools.names.${name}`, { defaultValue: name })
}

/** Whether `me` may read runs at all (`ai.use`: their own and their agents';
 *  `agent.manage`: every one). Which run a reader sees, the API decides. */
export function readsRuns(me: Me | null | undefined): boolean {
  return hasPermission(me, 'ai.use') || hasPermission(me, 'agent.manage')
}
