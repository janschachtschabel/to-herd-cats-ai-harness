import type { TFunction } from 'i18next'
import type { Conversation, Schemas } from '@/lib/api'

export type AgentStatus = Schemas['AgentStatus']
export const AGENT_STATUSES: readonly AgentStatus[] = ['draft', 'active', 'paused']

/** The system message an agent's run leaves when it stops without an answer. */
export const RUN_STOPPED = 'run.stopped'

const STOP_REASONS = [
  'completed',
  'max_steps',
  'deadline',
  'no_progress',
  'rights_revoked',
  'policy_blocked',
  'provider_refused',
  'error',
] as const

/** Why a run ended, in words (an unknown reason gets a general sentence). */
export function stopText(t: TFunction, reason: string | null | undefined): string {
  const known = (STOP_REASONS as readonly string[]).includes(reason ?? '')
  return t(`agents.stop.${known ? (reason as string) : 'unknown'}`)
}

const NO_RUN_REASONS = [
  'ai.unavailable',
  'agent.draft',
  'agent.paused',
  'agent.responsible_inactive',
  'agent.connection_unavailable',
  'run.thread_reply',
] as const

/** Why sending started no run (`agent_run.reason`), in words. */
export function noRunText(t: TFunction, reason: string): string {
  const known = (NO_RUN_REASONS as readonly string[]).includes(reason)
  return t(`agents.noRun.${known ? reason.replace('.', '_') : 'unknown'}`)
}

/** The agent of a direct message with one, else null. */
export function agentOf(conversation: Conversation): { id: string; name: string } | null {
  if (conversation.kind !== 'dm') return null
  const agent = (conversation.participants ?? []).find((p) => p.type === 'agent')
  return agent ? { id: agent.id, name: agent.name } : null
}

/** What a tool answers when it found nothing it may show (the backend's NOT_FOUND). */
const NOT_FOUND = 'Nothing found (or not readable).'

/** The sources an answer used: the pages and tickets its run read (found ones only),
 *  and how many results were redacted for the reader (spaces they may not read). */
export function sourcesOf(events: readonly Schemas['RunEventOut'][]): Sources {
  const seen = new Set<string>()
  const sources: Source[] = []
  let hidden = 0
  for (const event of events) {
    if (event.kind !== 'tool_call') continue
    const content = event.content as { source?: unknown; attrs?: Record<string, unknown> }
    if (event.redacted) {
      if (content.source === 'wiki' || content.source === 'ticket') hidden += 1
      continue
    }
    const text = (event.content as { text?: unknown }).text
    if (text === NOT_FOUND) continue
    const attrs = content.attrs ?? {}
    const source =
      content.source === 'wiki' && typeof attrs.id === 'string'
        ? ({ kind: 'page', id: attrs.id } as const)
        : content.source === 'ticket' && typeof attrs.key === 'string'
          ? ({ kind: 'ticket', key: attrs.key } as const)
          : null
    if (!source) continue
    const key = source.kind === 'page' ? `page:${source.id}` : `ticket:${source.key}`
    if (seen.has(key)) continue
    seen.add(key)
    sources.push(source)
  }
  return { sources, hidden }
}

export type Source = { kind: 'page'; id: string } | { kind: 'ticket'; key: string }
export type Sources = { sources: Source[]; hidden: number }
