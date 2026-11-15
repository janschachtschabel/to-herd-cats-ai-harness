import { hasPermission } from '@/features/auth/queries'
import type { Me, Space } from '@/lib/api'

/** What a person may do with automations before one exists, decided only from
 *  `/auth/me` permissions and a space's `my_role` (CLAUDE.md rule 12); for one that
 *  exists the API's `abilities` say it. The server checks every action again.
 *
 *  - `list`: "my automations" and a space's list (`ai.use`, or `agent.manage` who sees
 *    them all); in a space only with a role there (or `agent.manage`).
 *  - `create`: `ai.use` (in a space: with a role there; posting is the viewer's right).
 *  - `event`: event rules, only for who manages the space (`space.manage` = admin). */
export interface AutomationAbilities {
  list: boolean
  create: boolean
  event: boolean
}

export function automationAbilities(me: Me | null, space: Space | null): AutomationAbilities {
  const ai = hasPermission(me, 'ai.use')
  const all = hasPermission(me, 'agent.manage')
  if (!space) return { list: ai || all, create: ai, event: false }
  const member = space.my_role !== null
  return {
    list: all || (ai && member),
    create: ai && member,
    event: ai && space.my_role === 'admin',
  }
}
