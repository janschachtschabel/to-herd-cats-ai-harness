import type { Me, Space, SpaceRole } from '@/lib/api'

/** What a person may do with skills, decided only from `/auth/me` permissions and a
 *  space's `my_role` (CLAUDE.md rule 12); the server checks every action again.
 *  Mirrors `modules/skills`: reading needs `ai.use` (and the space) or `skill.manage`;
 *  managing a space's skills needs `skill.manage`, or `page.moderate` there with AI;
 *  organisation-wide skills only `skill.manage`. */
export interface SkillAbilities {
  read: boolean
  manage: boolean
}

const MODERATING: readonly SpaceRole[] = ['moderator', 'admin']

function holds(me: Me | null, permission: 'ai.use' | 'skill.manage'): boolean {
  return me?.permissions.includes(permission) ?? false
}

/** For the skills of `space`; `null`: the organisation-wide ones. */
export function skillAbilities(me: Me | null, space: Space | null): SkillAbilities {
  const admin = holds(me, 'skill.manage')
  const ai = holds(me, 'ai.use')
  if (!space) return { read: admin || ai, manage: admin }
  const member = space.my_role !== null
  return {
    read: admin || (ai && member),
    manage: admin || (ai && space.my_role !== null && MODERATING.includes(space.my_role)),
  }
}
