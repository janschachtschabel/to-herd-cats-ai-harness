import type { Schemas } from '@/lib/api'

export type AgentTool = Schemas['AgentToolOut']
export type Grant = Schemas['Grant']
export type AgentSkill = Schemas['AgentSkillOut']

/** The autonomy levels (spec 8.2): M6's three, and level 4 (acting outside) with the
 *  external tools of M8. */
export const LEVELS = [1, 2, 3, 4] as const
export type Level = (typeof LEVELS)[number]

/** The levels to offer: up to the highest the API lets this person give (`max_level`);
 *  a current level above that stays shown, so it can be kept or lowered. */
export function offeredLevels(maxLevel: number, current: number): Level[] {
  const top = Math.max(maxLevel, current)
  return LEVELS.filter((level) => level <= top)
}

/** What an entry can be for a tool: none (the level's default), or tighter. A tool the
 *  level blocks takes no entry at all: it is not available. */
export type EntryChoice = 'default' | 'confirm' | 'block'

export function entryChoices(tool: AgentTool): EntryChoice[] {
  if (tool.default === 'block') return []
  return ['default', 'confirm', 'block']
}

export function choiceOf(entry: Grant | null): EntryChoice {
  return entry === 'confirm' || entry === 'block' ? entry : 'default'
}

/** An external tool (plan M8) is offered only with an entry: not granted (no entry),
 *  allowed, or only after release. A writing one is at most "only after release". */
export type ExternalChoice = 'off' | 'allow' | 'confirm'

export function externalChoices(tool: AgentTool): ExternalChoice[] {
  return tool.effect === 'write' ? ['off', 'confirm'] : ['off', 'allow', 'confirm']
}

export function externalChoiceOf(entry: Grant | null): ExternalChoice {
  return entry === 'allow' || entry === 'confirm' ? entry : 'off'
}

export type AnyChoice = EntryChoice | ExternalChoice

/** The external tools grouped by server, in the order the API lists them (after the
 *  catalog); the catalog's own tools stay apart. */
export function splitTools(tools: readonly AgentTool[]): {
  builtIn: AgentTool[]
  servers: { id: string; name: string; tools: AgentTool[] }[]
} {
  const builtIn: AgentTool[] = []
  const servers: { id: string; name: string; tools: AgentTool[] }[] = []
  for (const tool of tools) {
    const remote = tool.external
    if (!remote) {
      builtIn.push(tool)
      continue
    }
    let group = servers.find((s) => s.id === remote.server_id)
    if (!group) {
      group = { id: remote.server_id, name: remote.server_name, tools: [] }
      servers.push(group)
    }
    group.tools.push(tool)
  }
  return { builtIn, servers }
}

/** The body of `PUT …/tools`: an entry for every tool not left at its default, in the
 *  catalog's order (an `allow` entry adds nothing to a catalog tool's default, so it is
 *  dropped); an external tool's entry unless it is not granted. */
export function toolEntries(
  tools: readonly AgentTool[],
  draft: Readonly<Record<string, AnyChoice>>,
): Schemas['AgentToolEntry'][] {
  return tools.flatMap((tool): Schemas['AgentToolEntry'][] => {
    if (tool.external) {
      const choice = draft[tool.name] ?? externalChoiceOf(tool.entry)
      return choice === 'off' || choice === 'default' || choice === 'block'
        ? []
        : [{ tool: tool.name, policy: choice }]
    }
    const choice = draft[tool.name] ?? choiceOf(tool.entry)
    return choice === 'default' || choice === 'off' || choice === 'allow'
      ? []
      : [{ tool: tool.name, policy: choice }]
  })
}

/** Why an assigned skill is not available to the agent now. */
export function unavailableReason(skill: AgentSkill): 'archived' | 'unreachable' | null {
  if (skill.available) return null
  return skill.state === 'archived' ? 'archived' : 'unreachable'
}
