import { hasPermission } from '@/features/auth/queries'
import type { Me } from '@/lib/api'
import { useAgents, type Agent } from '../queries'

/** Whether `me` may make personal agents (`agent.create_personal`: AI, and the
 *  organisation has not switched them off). */
export function createsPersonal(me: Me | null | undefined): boolean {
  return hasPermission(me, 'agent.create_personal')
}

/** My own agents: the API lists one's personal agents to people with AI (and every
 *  agent to agent admins, of which only their own are kept here). */
export function useMyAgents(meId: string | undefined) {
  const agents = useAgents()
  const mine = agents.items.filter((agent: Agent) => agent.owner_user_id === meId)
  return { ...agents, items: mine }
}
