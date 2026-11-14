import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '@/lib/format'
import type { SkillProposal } from './queries'

/** How a decided proposal ended: who accepted or rejected it and when (with the
 *  reason), and a link to the skill it changed or made. */
export function SkillProposalOutcome({ proposal }: { proposal: SkillProposal }) {
  const { t, i18n } = useTranslation()
  if (proposal.state === 'open') return null
  const who = proposal.decided_by?.name ?? t('proposals.unknownAuthor')
  const when = proposal.decided_at ? formatDateTime(proposal.decided_at, i18n.language) : ''
  return (
    <section aria-labelledby="skill-proposal-outcome" className="rounded-lg border p-3 text-sm">
      <h2 id="skill-proposal-outcome" className="font-medium">
        {t(`proposals.outcome.${proposal.state}`, { name: who, when })}
      </h2>
      {proposal.decision_reason && (
        <p className="mt-1 break-words">
          {t('proposals.outcome.reason', { reason: proposal.decision_reason })}
        </p>
      )}
      {proposal.state === 'accepted' && proposal.skill_id && (
        <Link
          to="/skills/$skillId"
          params={{ skillId: proposal.skill_id }}
          className="mt-1 inline-block underline underline-offset-4"
        >
          {proposal.result_number
            ? t('skills.proposals.openVersion', {
                name: proposal.name ?? '',
                number: proposal.result_number,
              })
            : t('skills.proposals.openSkill', { name: proposal.name ?? '' })}
        </Link>
      )}
    </section>
  )
}
