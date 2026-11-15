import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { useWiki } from '@/features/wiki/WikiContext'
import { formatDateTime } from '@/lib/format'
import type { Proposal } from './queries'

/** How a decided proposal ended: who accepted or rejected it and when (with the
 *  rejection's reason), and a link to the page it changed or created. */
export function ProposalOutcome({ proposal }: { proposal: Proposal }) {
  const { t, i18n } = useTranslation()
  const { space, nodes } = useWiki()
  if (proposal.state === 'open') return null
  const who = proposal.decided_by?.name ?? t('proposals.unknownAuthor')
  const when = proposal.decided_at ? formatDateTime(proposal.decided_at, i18n.language) : ''
  const page = nodes.find((n) => n.id === proposal.page_id)
  return (
    <section aria-labelledby="proposal-outcome" className="rounded-lg border p-3 text-sm">
      <h3 id="proposal-outcome" className="font-medium">
        {proposal.state === 'withdrawn'
          ? t('proposals.outcome.withdrawn')
          : t(`proposals.outcome.${proposal.state}`, { name: who, when })}
      </h3>
      {proposal.decision_reason && (
        <p className="mt-1">
          {t('proposals.outcome.reason', { reason: proposal.decision_reason })}
        </p>
      )}
      {proposal.state === 'accepted' && page && (
        <Link
          to="/spaces/$spaceId/p/$"
          params={{ spaceId: space.id, _splat: page.path }}
          className="mt-1 inline-block underline underline-offset-4"
        >
          {proposal.result_version
            ? t('proposals.outcome.openVersion', {
                title: page.title,
                number: proposal.result_version,
              })
            : t('proposals.outcome.openPage', { title: page.title })}
        </Link>
      )}
    </section>
  )
}
