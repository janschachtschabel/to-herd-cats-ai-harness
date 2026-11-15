import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { ViaToken } from '@/features/tokens/ViaToken'
import type { Proposal } from './queries'

/** Who proposed it; an agent carries the AI mark (everyone sees it), as does one made
 *  through an access token, with the token's name. */
export function ProposalAuthor({ proposal }: { proposal: Proposal }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {t('proposals.by', { name: proposal.author.name ?? t('proposals.unknownAuthor') })}
      {proposal.ai && <AgentBadge />}
      {proposal.via_token && <ViaToken name={proposal.via_token} />}
    </span>
  )
}
