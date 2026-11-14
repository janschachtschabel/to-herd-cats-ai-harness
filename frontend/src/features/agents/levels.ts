import type { Schemas } from '@/lib/api'

export type AgentTool = Schemas['AgentToolOut']
export type Grant = Schemas['Grant']
export type AgentSkill = Schemas['AgentSkillOut']

/** The autonomy levels of M6 (spec 8.2; level 4 comes with external tools in M8). */
export const LEVELS = [1, 2, 3] as const
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

/** The body of `PUT …/tools`: an entry for every tool not left at its default, in the
 *  catalog's order (an `allow` entry adds nothing to the default, so it is dropped). */
export function toolEntries(
  tools: readonly AgentTool[],
  draft: Readonly<Record<string, EntryChoice>>,
): Schemas['AgentToolEntry'][] {
  return tools.flatMap((tool) => {
    const choice = draft[tool.name] ?? choiceOf(tool.entry)
    return choice === 'default' ? [] : [{ tool: tool.name, policy: choice }]
  })
}

/** Why an assigned skill is not available to the agent now. */
export function unavailableReason(skill: AgentSkill): 'archived' | 'unreachable' | null {
  if (skill.available) return null
  return skill.state === 'archived' ? 'archived' : 'unreachable'
}
