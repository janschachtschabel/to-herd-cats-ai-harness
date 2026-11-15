import type { Run, RunEvent } from '@/features/agents/queries'

/** A tool call the model asked for in a step. */
export interface AskedCall {
  id: string
  name: string
  args: unknown
}

/** One row of a run's timeline, built from its journal (`run_event`). */
export type TimelineItem =
  | {
      kind: 'model'
      key: string
      step: number
      text: string | null
      calls: AskedCall[]
      event: RunEvent
    }
  | {
      kind: 'tool'
      key: string
      step: number
      name: string
      args: unknown
      result: string | null
      source: string | null
      final: boolean
      /** An external server's tool (`source` mcp): its server and its own name. */
      external: { server: string; tool: string } | null
      /** An external call's state when its result says so: still being sent, its
       *  answer never recorded (`unknown`), or why it was not made or failed. */
      outcome: ExternalOutcome | 'sending' | null
      event: RunEvent
    }
  /** A call that has no result yet while the run waits: for a release or an answer. */
  | { kind: 'waiting'; key: string; step: number; call: AskedCall }
  | { kind: 'stop'; key: string; reason: string | null; detail: string | null; event: RunEvent }
  | { kind: 'mark'; key: string; event: RunEvent }

/** What an external call's result says (the host's fixed words, never the server's). */
export type ExternalOutcome =
  | 'unknown'
  | 'not_connected'
  | 'unavailable'
  | 'credential_unavailable'
  | 'failed'
  | 'error'
  | 'policy'

const OUTCOME_PREFIXES: readonly [string, ExternalOutcome][] = [
  ['external_outcome_unknown', 'unknown'],
  ['external_tool_not_connected', 'not_connected'],
  ['external_tool_unavailable', 'unavailable'],
  ['external_tool_credential_unavailable', 'credential_unavailable'],
  ['external_tool_failed', 'failed'],
  ['external_tool_error', 'error'],
  ['policy_blocked', 'policy'],
]

export function externalOutcome(result: string | null): ExternalOutcome | null {
  if (!result) return null
  return OUTCOME_PREFIXES.find(([prefix]) => result.startsWith(`${prefix}:`))?.[1] ?? null
}

const EXTERNAL_NAME = /^ext_(?:[0-9a-f]{32}|[0-9a-f]{12})_(.+)$/

/** An external tool's own name from the name a run gives it (`ext_<id>_<name>`, the
 * id whole; runs of an earlier release: its first 12 hex). */
export function externalToolName(name: string): string | null {
  return EXTERNAL_NAME.exec(name)?.[1] ?? null
}

function attrsOf(value: unknown): { server: string; tool: string } | null {
  if (typeof value !== 'object' || value === null) return null
  const a = value as Record<string, unknown>
  return typeof a.server === 'string' && typeof a.tool === 'string'
    ? { server: a.server, tool: a.tool }
    : null
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

function num(value: unknown): number {
  return typeof value === 'number' ? value : 0
}

function calls(value: unknown): AskedCall[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((call) => {
    if (typeof call !== 'object' || call === null) return []
    const c = call as Record<string, unknown>
    const name = text(c.name)
    return name ? [{ id: text(c.id) ?? '', name, args: c.args }] : []
  })
}

/**
 * The rows of a run's timeline in the order they happened: each model step with the
 * calls it asked for, each call's result, the stop. An external call is journaled
 * twice under one call id (once when sent, "outcome unknown", then with its result):
 * it is one row, where it was sent, with its latest entry; an unknown outcome that is
 * the run's last entry while it still runs is "being sent". While the run waits, the
 * calls of its last step that have no result yet are shown as waiting (for a release
 * or an answer). A redacted event keeps only its step and name; its rows say so. A
 * `mark` event (the run's history held personal messages) is a row of its own. A kind
 * this version does not know (a newer release's) is passed over.
 */
export function buildTimeline(events: readonly RunEvent[], run: Run): TimelineItem[] {
  const items: TimelineItem[] = []
  const answered = new Set<string>()
  const toolAt = new Map<string, number>()
  let last: { step: number; calls: AskedCall[] } | null = null
  for (const event of events) {
    const content = event.content as Record<string, unknown>
    const step = num(content.step)
    if (event.kind === 'model_call') {
      const asked = calls(content.tool_calls)
      last = { step, calls: asked }
      items.push({
        kind: 'model',
        key: event.id,
        step,
        text: text(content.text),
        calls: asked,
        event,
      })
    } else if (event.kind === 'tool_call') {
      const callKey = `${step}:${text(content.call_id) ?? ''}`
      answered.add(callKey)
      const source = text(content.source)
      const result = text(content.text)
      const item: TimelineItem = {
        kind: 'tool',
        key: event.id,
        step,
        name: text(content.name) ?? '',
        args: content.args,
        result,
        source,
        final: content.final === true,
        external: source === 'mcp' ? attrsOf(content.attrs) : null,
        outcome: source === 'mcp' ? externalOutcome(result) : null,
        event,
      }
      const at = text(content.call_id) ? toolAt.get(callKey) : undefined
      if (at === undefined) {
        toolAt.set(callKey, items.length)
        items.push(item)
      } else {
        items[at] = { ...item, key: items[at]!.key }
      }
    } else if (event.kind === 'mark') {
      items.push({ kind: 'mark', key: event.id, event })
    } else if (event.kind === 'stop') {
      items.push({
        kind: 'stop',
        key: event.id,
        reason: text(content.reason),
        detail: text(content.detail),
        event,
      })
    }
  }
  const lastItem = items.at(-1)
  if (
    run.state !== 'done' &&
    lastItem?.kind === 'tool' &&
    lastItem.outcome === 'unknown' &&
    lastItem.event === events.at(-1)
  ) {
    items[items.length - 1] = { ...lastItem, outcome: 'sending' }
  }
  if (run.state === 'waiting' && last) {
    for (const call of last.calls) {
      if (answered.has(`${last.step}:${call.id}`)) continue
      items.push({ kind: 'waiting', key: `waiting-${call.id}`, step: last.step, call })
    }
  }
  return items
}

/** What a release step answered the model: rejected or stale (the object changed). */
export function approvalOutcome(result: string | null): 'rejected' | 'stale' | null {
  if (result?.startsWith('approval_rejected')) return 'rejected'
  if (result?.startsWith('approval_stale')) return 'stale'
  return null
}

/** A value as readable, indented JSON for the folded parts of a step. */
export function readable(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
