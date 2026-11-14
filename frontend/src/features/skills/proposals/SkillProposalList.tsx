import { Link } from '@tanstack/react-router'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { SkillAuthor } from '../SkillAuthor'
import { SKILL_PROPOSAL_STATES, skillProposalTitle, skillProposalWhere } from './display'
import { useSkillProposals, type SkillProposalFilter, type SkillProposalState } from './queries'

/** Proposals for skills that agents made, by state (open first); each opens its own
 *  page, where those who may decide accept or reject it. `children`: more filters. */
export function SkillProposalList({
  filter,
  spaceNames,
  children,
}: {
  filter: Omit<SkillProposalFilter, 'state'>
  spaceNames?: ReadonlyMap<string, string>
  children?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const [state, setState] = useState<SkillProposalState>('open')
  const proposals = useSkillProposals({ ...filter, state })
  return (
    <section aria-labelledby="skill-proposals-heading">
      <h2 id="skill-proposals-heading" className="sr-only">
        {t('skills.proposals.title')}
      </h2>
      <p className="mb-3 text-sm text-muted-foreground">{t('skills.proposals.hint')}</p>
      <div className="mb-4 grid gap-3 sm:grid-cols-[10rem_minmax(0,12rem)]">
        <Field label={t('skills.filter.state')}>
          {(props) => (
            <NativeSelect
              {...props}
              value={state}
              onChange={(e) => setState(e.target.value as SkillProposalState)}
            >
              {SKILL_PROPOSAL_STATES.map((value) => (
                <option key={value} value={value}>
                  {t(`proposals.states.${value}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        {children}
      </div>
      {proposals.isPending ? (
        <LoadingState />
      ) : proposals.isError ? (
        <ErrorState error={proposals.error} onRetry={() => void proposals.refetch()} />
      ) : proposals.items.length === 0 ? (
        <EmptyState text={t(`skills.proposals.empty.${state}`)} />
      ) : (
        <ul aria-label={t('skills.proposals.title')} className="divide-y rounded-lg border">
          {proposals.items.map((proposal) => (
            <li key={proposal.id} className="flex flex-col gap-1 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/skill-proposals/$proposalId"
                  params={{ proposalId: proposal.id }}
                  className="font-medium break-words underline-offset-4 hover:underline"
                >
                  {skillProposalTitle(t, proposal)}
                </Link>
                <Badge variant="outline">{skillProposalWhere(t, proposal, spaceNames)}</Badge>
              </div>
              <p className="break-words">{proposal.reason}</p>
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <SkillAuthor author={proposal.author} />
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
