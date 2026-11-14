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
