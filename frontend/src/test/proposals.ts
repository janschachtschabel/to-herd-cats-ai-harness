import type { Schemas } from '@/lib/api'

type Proposal = Schemas['ProposalOut']
type ProposalDetail = Schemas['ProposalDetailOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-7${String(++counter).padStart(11, '0')}`

export function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: id(),
    space_id: 'space-1',
    kind: 'change',
    state: 'open',
    page_id: 'page-1',
    parent_id: null,
    title: null,
    base_version: 3,
    reason: 'Die Frist ist jetzt 30 Tage.',
    author: { type: 'agent', id: 'agent-1', name: 'Hilda' },
    ai: true,
    run_id: null,
    decided_by: null,
    decided_at: null,
    decision_reason: null,
    result_version: null,
    version: 1,
    created_at: '2026-11-14T08:00:00Z',
    ...overrides,
  }
}

export function makeProposalDetail(overrides: Partial<ProposalDetail> = {}): ProposalDetail {
  return {
    ...makeProposal(overrides),
    content_md: '# Urlaub\n\n30 Tage.',
    diff: [
      { kind: 'equal', lines: ['# Urlaub', ''] },
      { kind: 'delete', lines: ['28 Tage.'] },
      { kind: 'insert', lines: ['30 Tage.'] },
    ],
    too_large: false,
    page_version: 5,
    current_content_md: null,
    merge: null,
    ...overrides,
  }
}
