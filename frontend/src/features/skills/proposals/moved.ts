import { ApiError } from '@/lib/api'
import type { SkillProposalDetail } from './queries'

interface Text {
  description: string
  content: string
}

/** What accepting a proposal needs once its skill moved on: the skill's `version` to
 *  name (`skill_version`), its text now and the proposed text. */
export interface Moved {
  skillVersion: number
  current: Text
  proposed: Text
}

function text(value: unknown): Text | null {
  if (typeof value !== 'object' || value === null) return null
  const t = value as Record<string, unknown>
  if (typeof t.description !== 'string' || typeof t.content !== 'string') return null
  return { description: t.description, content: t.content }
}

/** Both texts in a 409 `skill_proposal.base_outdated`, or null for any other error. */
export function movedFrom(error: unknown): Moved | null {
  if (!(error instanceof ApiError) || error.code !== 'skill_proposal.base_outdated') return null
  const d = error.details ?? {}
  const current = text(d.current)
  const proposed = text(d.proposed)
  if (typeof d.skill_version !== 'number' || !current || !proposed) return null
  return { skillVersion: d.skill_version, current, proposed }
}

/** The same from an open proposal that already says its skill moved on. */
export function movedOf(proposal: SkillProposalDetail): Moved | null {
  if (!proposal.outdated || !proposal.current || proposal.state !== 'open') return null
  const { version, description, content } = proposal.current
  return { skillVersion: version, current: { description, content }, proposed: proposal.proposed }
}
