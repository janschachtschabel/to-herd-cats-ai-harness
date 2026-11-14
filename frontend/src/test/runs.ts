import type { Schemas } from '@/lib/api'

type Run = Schemas['RunOut']
type RunEvent = Schemas['RunEventOut']
type Approval = Schemas['ApprovalOut']
type Question = Schemas['QuestionOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-9${String(++counter).padStart(11, '0')}`

export const HILDA = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }

export function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: id(),
    agent_id: HILDA.id,
    agent_name: HILDA.name,
    asker_id: 'asker',
    asker_name: 'Jan Jansen',
    conversation_id: 'c-1',
    place: {
      kind: 'thread_ticket',
      conversation_id: 'c-1',
      space_id: 'space-1',
      page_id: null,
      ticket_number: 7,
    },
    state: 'done',
    stop_reason: 'completed',
    attempt: 1,
    recoveries: 0,
    steps: 2,
    chain_depth: 0,
    trigger_message_id: null,
    created_at: '2026-11-14T09:00:00Z',
    started_at: '2026-11-14T09:00:00Z',
    finished_at: '2026-11-14T09:00:12Z',
    wait_until: null,
    cancel_requested: false,
    usage: { calls: 2, tokens_in: 1200, tokens_out: 300, tokens_cached: 200, cost: '0.0123' },
    ...overrides,
  }
}

export function makeEvent(overrides: Partial<RunEvent> = {}): RunEvent {
  return {
    id: id(),
    attempt: 1,
    seq: 1,
    kind: 'model_call',
    content: {},
    redacted: false,
    tokens_in: null,
    tokens_out: null,
    tokens_cached: null,
    cost: null,
    duration_ms: null,
    created_at: '2026-11-14T09:00:01Z',
    ...overrides,
  }
}

export function makeApproval(overrides: Partial<Approval> = {}): Approval {
  return {
    id: id(),
    run_id: 'run-1',
    conversation_id: 'c-1',
    message_id: 'm-1',
    tool: 'propose_page_change',
    summary: 'propose_page_change: page_id=p-1',
    args: { page_id: 'p-1', reason: 'Neue Frist' },
    diff_url: '/api/approvals/x/diff',
    state: 'pending',
    addressed_to: 'asker',
    decided_by: null,
    decided_at: null,
    reason: null,
    expires_at: '2026-11-17T09:00:00Z',
    created_at: '2026-11-14T09:00:00Z',
    version: 1,
    ...overrides,
  }
}

export function makeQuestion(overrides: Partial<Question> = {}): Question {
  return {
    id: id(),
    run_id: 'run-1',
    conversation_id: 'c-1',
    message_id: 'm-2',
    question: 'Für welches Jahr?',
    state: 'pending',
    addressed_to: 'asker',
    answer: null,
    answered_at: null,
    expires_at: '2026-11-17T09:00:00Z',
    created_at: '2026-11-14T09:00:00Z',
    version: 1,
    ...overrides,
  }
}
