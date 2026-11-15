import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import { formatDateTime } from '@/lib/format'
import { PROPOSAL_STATES, proposalTitle } from './display'
import { ProposalAuthor } from './ProposalAuthor'
import { useProposals, type ProposalState } from './queries'

/** A space's proposals for its page editors: the open ones first (the tab counts
 *  them), the decided ones by state. Moderators decide on each proposal's own page. */
export function ProposalsView() {
  const { t, i18n } = useTranslation()
  const { space, nodes, abilities } = useWiki()
  const [state, setState] = useState<ProposalState>('open')
  const proposals = useProposals(space.id, state, abilities.edit)

  if (!abilities.edit) return <EmptyState text={t('proposals.noAccess')} />
  return (
    <section aria-labelledby="proposals-heading">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="proposals-heading" className="text-lg font-semibold">
            {t('proposals.title')}
          </h2>
          <p className="text-sm text-muted-foreground">
            {abilities.moderate ? t('proposals.hintModerator') : t('proposals.hintEditor')}
          </p>
        </div>
        <div className="w-44">
          <Field label={t('proposals.filter')}>
            {(props) => (
              <NativeSelect
                {...props}
                value={state}
                onChange={(e) => setState(e.target.value as ProposalState)}
              >
                {PROPOSAL_STATES.map((value) => (
                  <option key={value} value={value}>
                    {t(`proposals.states.${value}`)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
        </div>
      </div>
      {proposals.isPending ? (
        <LoadingState />
      ) : proposals.isError ? (
        <ErrorState error={proposals.error} onRetry={() => void proposals.refetch()} />
      ) : proposals.items.length === 0 ? (
        <EmptyState text={t(`proposals.empty.${state}`)} />
      ) : (
        <ul aria-label={t('proposals.title')} className="divide-y rounded-lg border">
          {proposals.items.map((proposal) => (
            <li key={proposal.id} className="flex flex-col gap-1 p-3 text-sm">
              <Link
                to="/spaces/$spaceId/proposals/$proposalId"
                params={{ spaceId: space.id, proposalId: proposal.id }}
                className="font-medium underline-offset-4 hover:underline"
              >
                {proposalTitle(t, proposal, nodes)}
              </Link>
              <p>{proposal.reason}</p>
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <ProposalAuthor proposal={proposal} />
                <span>{formatDateTime(proposal.created_at, i18n.language)}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={proposals.hasMore}
        loading={proposals.loadingMore}
        onLoad={proposals.loadMore}
      />
    </section>
  )
}
