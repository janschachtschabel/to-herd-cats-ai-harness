import { describe, expect, test } from 'vitest'
import { makeEvent, makeRun } from '@/test/runs'
import { buildTimeline, externalOutcome, externalToolName } from './timeline'

const TOOL = 'ext_0123456789ab_create_issue'
const UNKNOWN =
  'external_outcome_unknown: this call was sent to the external server, but its answer was never recorded.'

const model = makeEvent({
  kind: 'model_call',
  seq: 1,
  content: { step: 1, tool_calls: [{ id: 'c1', name: TOOL, args: { repo: 'acme/app' } }] },
})
const sent = makeEvent({
  kind: 'tool_call',
  seq: 2,
  duration_ms: 0,
  content: {
    step: 1,
    call_id: 'c1',
    name: TOOL,
    args: { repo: 'acme/app' },
    source: 'mcp',
    attrs: { server: 'GitHub', tool: 'create_issue' },
    text: UNKNOWN,
  },
})
const answered = makeEvent({
  kind: 'tool_call',
  seq: 3,
  duration_ms: 812,
  content: { ...sent.content, text: '{"number": 42}' },
})

describe('external calls in a run’s timeline', () => {
  test('two entries for one call are one row with the latest state, where it was sent', () => {
    const items = buildTimeline([model, sent, answered], makeRun())
    const tools = items.filter((item) => item.kind === 'tool')
    expect(tools).toHaveLength(1)
    expect(items.indexOf(tools[0]!)).toBe(1)
    expect(tools[0]).toMatchObject({
      result: '{"number": 42}',
      external: { server: 'GitHub', tool: 'create_issue' },
      outcome: null,
    })
    expect(tools[0]!.event.duration_ms).toBe(812)
  })

  test('a call whose answer never came: unknown once the run went on or ended', () => {
    const done = buildTimeline([model, sent], makeRun({ state: 'done' }))
    expect(done.find((item) => item.kind === 'tool')).toMatchObject({ outcome: 'unknown' })
    const later = makeEvent({ kind: 'model_call', seq: 4, content: { step: 2 } })
    const goingOn = buildTimeline([model, sent, later], makeRun({ state: 'running' }))
    expect(goingOn.find((item) => item.kind === 'tool')).toMatchObject({ outcome: 'unknown' })
  })

  test('while the run is still at it, the last call is being sent', () => {
    const items = buildTimeline([model, sent], makeRun({ state: 'running', stop_reason: null }))
    expect(items.find((item) => item.kind === 'tool')).toMatchObject({ outcome: 'sending' })
  })

  test('what an external result says, as a word', () => {
    expect(externalOutcome(UNKNOWN)).toBe('unknown')
    expect(externalOutcome('external_tool_not_connected: …')).toBe('not_connected')
    expect(externalOutcome('external_tool_unavailable: …')).toBe('unavailable')
    expect(externalOutcome('external_tool_credential_unavailable: …')).toBe(
      'credential_unavailable',
    )
    expect(externalOutcome('external_tool_failed: … (timeout).')).toBe('failed')
    expect(externalOutcome('external_tool_error: the tool reported an error.\nx')).toBe('error')
    expect(externalOutcome('policy_blocked: what this run has read …')).toBe('policy')
    expect(externalOutcome('{"ok": true}')).toBeNull()
  })

  test('an external tool’s own name from its run name', () => {
    expect(externalToolName(TOOL)).toBe('create_issue')
    expect(externalToolName('ext_0123456789abcdef0123456789abcdef_get_items')).toBe('get_items')
    expect(externalToolName('search')).toBeNull()
  })
})

describe('event kinds this version does not know', () => {
  test('are passed over, never shown as a stop (module review M8 3, H6)', () => {
    const later = makeEvent({
      kind: 'from_the_future' as unknown as 'stop',
      seq: 4,
      content: { reason: 'completed' },
    })
    const stop = makeEvent({ kind: 'stop', seq: 5, content: { reason: 'completed' } })
    const items = buildTimeline([model, answered, later, stop], makeRun({ state: 'done' }))
    expect(items.map((item) => item.kind)).toEqual(['model', 'tool', 'stop'])
  })
})
