import type { TFunction } from 'i18next'
import type { TreeNode } from '@/lib/api'
import type { Proposal, ProposalState } from './queries'

export const PROPOSAL_STATES: readonly ProposalState[] = [
  'open',
  'accepted',
  'rejected',
  'withdrawn',
]

/** What a proposal is about, in words: a change to a page (by its title in the tree),
 *  or a new page with its title and its parent. */
export function proposalTitle(
  t: TFunction,
  proposal: Proposal,
  nodes: readonly TreeNode[],
): string {
  const title = (id: string | null) => nodes.find((n) => n.id === id)?.title
  if (proposal.kind === 'new') {
    const parent = title(proposal.parent_id)
    return parent
      ? t('proposals.newPageUnder', { title: proposal.title ?? '', parent })
      : t('proposals.newPage', { title: proposal.title ?? '' })
  }
  return t('proposals.change', { title: title(proposal.page_id) ?? t('proposals.somePage') })
}

/** The open proposals about one page (changes to it), from the space's open list. */
export function openForPage(proposals: readonly Proposal[], pageId: string): number {
  return proposals.filter((p) => p.kind === 'change' && p.page_id === pageId).length
}

/** The tab's count: the open ones loaded, "100+" while more pages exist. */
export function countLabel(count: number, more: boolean): string {
  return more ? `${count}+` : String(count)
}
