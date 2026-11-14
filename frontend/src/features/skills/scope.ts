import type { SkillFilter } from './queries'

/** Where skills belong, as a select's value: every place, only the organisation, or
 *  one space (by id). */
export type Scope = 'all' | 'org' | (string & {})

export function scopeFilter(scope: Scope): Pick<SkillFilter, 'spaceId' | 'orgWide'> {
  if (scope === 'all') return {}
  if (scope === 'org') return { orgWide: true }
  return { spaceId: scope }
}

/** The space a new skill (or an import) goes to from a scope: none is the organisation. */
export function targetSpace(scope: Scope): string | null {
  return scope === 'all' || scope === 'org' ? null : scope
}
