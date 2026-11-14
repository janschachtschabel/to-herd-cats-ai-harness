import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import type { Proposal } from './queries'

/** Who proposed it; an agent carries the AI mark (everyone sees it). */
export function ProposalAuthor({ proposal }: { proposal: Proposal }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {t('proposals.by', { name: proposal.author.name ?? t('proposals.unknownAuthor') })}
      {proposal.ai && <AgentBadge />}
    </span>
  )
}
