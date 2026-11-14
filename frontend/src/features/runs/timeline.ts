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
      event: RunEvent
    }
  /** A call that has no result yet while the run waits: for a release or an answer. */
  | { kind: 'waiting'; key: string; step: number; call: AskedCall }
  | { kind: 'stop'; key: string; reason: string | null; detail: string | null; event: RunEvent }

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
 * calls it asked for, each call's result, the stop. While the run waits, the calls of
 * its last step that have no result yet are shown as waiting (for a release or an
 * answer). A redacted event keeps only its step and name; its rows say so.
 */
export function buildTimeline(events: readonly RunEvent[], run: Run): TimelineItem[] {
  const items: TimelineItem[] = []
  const answered = new Set<string>()
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
      answered.add(`${step}:${text(content.call_id) ?? ''}`)
      items.push({
        kind: 'tool',
        key: event.id,
        step,
        name: text(content.name) ?? '',
        args: content.args,
        result: text(content.text),
        source: text(content.source),
        final: content.final === true,
        event,
      })
    } else {
      items.push({
        kind: 'stop',
        key: event.id,
        reason: text(content.reason),
        detail: text(content.detail),
        event,
      })
    }
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
