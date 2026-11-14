import type { TFunction } from 'i18next'
import type { SkillProposal, SkillProposalState } from './queries'

export const SKILL_PROPOSAL_STATES: readonly SkillProposalState[] = ['open', 'accepted', 'rejected']

/** "New skill „name“" or "Change to „name“". */
export function skillProposalTitle(t: TFunction, proposal: SkillProposal): string {
  const name = proposal.name ?? t('skills.proposals.someSkill')
  return proposal.kind === 'new'
    ? t('skills.proposals.newSkill', { name })
    : t('skills.proposals.change', { name })
}

/** Where a proposal belongs: a space by name, or the organisation. */
export function skillProposalWhere(
  t: TFunction,
  proposal: Pick<SkillProposal, 'space_id'>,
  spaceNames?: ReadonlyMap<string, string>,
): string {
  if (!proposal.space_id) return t('skills.scope.org')
  return spaceNames?.get(proposal.space_id) ?? t('skills.scope.space')
}
