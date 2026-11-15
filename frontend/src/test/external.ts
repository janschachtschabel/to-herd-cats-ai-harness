import type { Schemas } from '@/lib/api'

type Agent = Schemas['AgentOut']
type Tool = Schemas['AgentToolOut']

export const EXTERNAL_ID = '00000000-0000-7000-8000-0000000000e1'

/** An external agent (plan M8): no connection, no model, level 2 at most. */
export function makeExternalAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: EXTERNAL_ID,
    name: 'Codi',
    intro: 'Arbeitet Tickets von außen ab.',
    kind: 'external',
    instructions: '',
    connection_id: null,
    model: null,
    responsible_user_id: '00000000-0000-7000-8000-0000000000b1',
    responsible_name: 'Ben Bauer',
    owner_user_id: null,
    status: 'active',
    max_steps: 25,
    max_runtime_seconds: 600,
    level: 2,
    version: 3,
    created_at: '2026-11-13T08:00:00Z',
    updated_at: '2026-11-13T08:00:00Z',
    ...overrides,
  }
}

function tool(name: string, level: number, effect: Tool['effect'], via_mcp: boolean): Tool {
  return {
    name,
    level,
    effect,
    default: level <= 2 ? 'allow' : 'block',
    entry: null,
    effective: level <= 2 ? 'allow' : 'block',
    external: null,
    via_mcp,
  }
}

/** An external agent's grants as the API lists them: every catalog tool, `via_mcp` on
 *  those its token can reach. */
export function externalTools(overrides: Partial<Schemas['AgentToolsOut']> = {}) {
  return {
    agent_id: EXTERNAL_ID,
    level: 2,
    max_level: 2,
    version: 3,
    tools: [
      tool('search', 1, 'read', true),
      tool('ask_user', 1, 'read', false),
      tool('update_memory', 2, 'write', false),
      tool('comment_ticket', 2, 'write', true),
      { ...tool('set_ticket_status', 2, 'write', true), entry: 'block', effective: 'block' },
      tool('update_page', 3, 'write', false),
    ],
    ...overrides,
  } satisfies Schemas['AgentToolsOut']
}
