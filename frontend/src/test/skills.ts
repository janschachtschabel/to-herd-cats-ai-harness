import type { Schemas } from '@/lib/api'

type Skill = Schemas['SkillOut']
type SkillDetail = Schemas['SkillDetailOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-5${String(++counter).padStart(11, '0')}`

export function makeSkill(overrides: Partial<Skill> = {}): Skill {
  return {
    id: id(),
    space_id: null,
    name: 'protokoll',
    description: 'Schreibt Protokolle.',
    state: 'active',
    author: { type: 'user', id: 'author', name: 'Lea Löwe' },
    version: 1,
    created_at: '2026-11-14T08:00:00Z',
    updated_at: '2026-11-14T08:00:00Z',
    ...overrides,
  }
}

export function makeSkillDetail(overrides: Partial<SkillDetail> = {}): SkillDetail {
  return { ...makeSkill(overrides), content: '# Protokoll\n\nKurz und klar.', ...overrides }
}

type SkillProposal = Schemas['SkillProposalOut']
type SkillProposalDetail = Schemas['SkillProposalDetailOut']

export function makeSkillProposal(overrides: Partial<SkillProposal> = {}): SkillProposal {
  return {
    id: id(),
    kind: 'change',
    space_id: null,
    skill_id: 'skill-1',
    name: 'protokoll',
    reason: 'Die Vorlage fehlt.',
    author: { type: 'agent', id: 'hilda', name: 'Hilda' },
    run_id: null,
    state: 'open',
    base_number: 1,
    decided_by: null,
    decided_at: null,
    decision_reason: null,
    result_number: null,
    version: 1,
    created_at: '2026-11-14T09:00:00Z',
    ...overrides,
  }
}

export function makeSkillProposalDetail(
  overrides: Partial<SkillProposalDetail> = {},
): SkillProposalDetail {
  return {
    ...makeSkillProposal(overrides),
    proposed: { description: 'Schreibt Protokolle.', content: '# Protokoll\n\nMit Vorlage.' },
    current: {
      description: 'Schreibt Protokolle.',
      content: '# Protokoll\n\nKurz und klar.',
      version: 1,
      number: 1,
    },
    outdated: false,
    ...overrides,
  }
}
