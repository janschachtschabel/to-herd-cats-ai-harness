import { describe, expect, test } from 'vitest'
import { externalTools } from '@/test/external'
import type { AgentTool } from '../levels'
import { choicesFor, entriesWith, reachable } from './choices'

describe("an external agent's grants", () => {
  test('only the tools its token can reach, allowed or blocked', () => {
    const tools = externalTools().tools
    expect(reachable(tools).map((t) => t.name)).toEqual([
      'search',
      'comment_ticket',
      'set_ticket_status',
    ])
    expect(choicesFor(tools[0]!)).toEqual(['allow', 'block'])
    const kept = { ...tools[0]!, entry: 'confirm', effective: 'confirm' } satisfies AgentTool
    expect(choicesFor(kept)).toEqual(['allow', 'confirm', 'block'])
  })

  test('saving keeps the entries not shown and drops an allow', () => {
    const remote: AgentTool = {
      name: 'ext_1_issues',
      level: 2,
      effect: 'read',
      default: 'block',
      entry: 'allow',
      effective: 'allow',
      external: { server_id: 's', server_name: 'S', tool_id: 't', tool_name: 'i', usable: true },
      via_mcp: false,
    }
    const tools = [...externalTools().tools, remote]
    expect(entriesWith(tools, { search: 'block', set_ticket_status: 'allow' })).toEqual([
      { tool: 'search', policy: 'block' },
      { tool: 'ext_1_issues', policy: 'allow' },
    ])
  })
})
