import type { Schemas } from '@/lib/api'
import type { AgentTool, Grant } from '../levels'

/** What an external agent's grant can be for a tool its token can reach: allowed (the
 *  level's default) or blocked. "Only after release" does not exist over `/mcp` (it
 *  counts as blocked there), so it is offered only to keep an entry that has it. */
export type ExternalAgentChoice = 'allow' | 'confirm' | 'block'

export function reachable(tools: readonly AgentTool[]): AgentTool[] {
  return tools.filter((tool) => tool.via_mcp && !tool.external)
}

export function choicesFor(tool: AgentTool): ExternalAgentChoice[] {
  if (tool.default === 'block') return []
  return tool.entry === 'confirm' ? ['allow', 'confirm', 'block'] : ['allow', 'block']
}

export function choiceOf(entry: Grant | null): ExternalAgentChoice {
  return entry === 'confirm' || entry === 'block' ? entry : 'allow'
}

/** The body of `PUT …/tools`: every entry the agent has, with the choices made here
 *  (`allow` adds nothing to the level's default, so it drops the entry); entries of
 *  tools not shown here are kept as they are. */
export function entriesWith(
  tools: readonly AgentTool[],
  draft: Readonly<Record<string, ExternalAgentChoice>>,
): Schemas['AgentToolEntry'][] {
  return tools.flatMap((tool): Schemas['AgentToolEntry'][] => {
    if (tool.external) return tool.entry ? [{ tool: tool.name, policy: tool.entry }] : []
    const chosen = draft[tool.name]
    const policy = chosen ?? tool.entry
    if (!policy || policy === 'allow') return []
    return [{ tool: tool.name, policy }]
  })
}
