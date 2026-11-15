import { hasPermission } from '@/features/auth/queries'
import type { Me, Schemas } from '@/lib/api'

export type Connection = Schemas['ConnectionOut']
export type ConnectionKind = Schemas['ConnectionKind']
export type DataLocation = Schemas['DataLocation']
export type Purpose = Schemas['Purpose']
export type ParamFamily = Schemas['ParamFamily']
export type AiPolicy = Schemas['AiPolicy']
export type CheckStatus = Schemas['CheckStatus']

export const CONNECTION_KINDS: readonly ConnectionKind[] = [
  'openai',
  'openai_compatible',
  'b_api',
  'local',
]
export const DATA_LOCATIONS: readonly DataLocation[] = ['local', 'eu', 'external']
export const PURPOSES: readonly Purpose[] = ['chat', 'embedding', 'both']
export const PARAM_FAMILIES: readonly ParamFamily[] = ['max_completion_tokens', 'max_tokens']
export const AI_POLICIES: readonly AiPolicy[] = ['any', 'restricted', 'none']

/** Whether `me` uses AI at all (`ai.use`): the only gate for AI in the person's own
 *  work (agents in the DM dialog, own usage, sources of an answer). */
export function usesAi(me: Me | null | undefined): boolean {
  return hasPermission(me, 'ai.use')
}

/** Whether the no-AI lock of content is shown to a reader: to people who use AI or
 *  administer it. Who governs content sees and sets its AI settings through that right
 *  alone, AI or not (space policy: `space.manage`; the lock: `page.moderate`).
 *  Everyone else sees nothing about AI. */
export function seesAiSettings(me: Me | null | undefined): boolean {
  return usesAi(me) || hasPermission(me, 'ai.manage')
}

/** A check's state as a tone for its badge. */
export function checkTone(status: CheckStatus): 'ok' | 'refused' | 'failed' {
  if (status === 'ok') return 'ok'
  if (['unauthorized', 'payment_required', 'forbidden', 'rate_limited'].includes(status)) {
    return 'refused'
  }
  return 'failed'
}

/** Connections that can answer in a chat (agents, assignments). */
export function chatConnections(connections: readonly Connection[]): Connection[] {
  return connections.filter((c) => c.purpose !== 'embedding')
}
