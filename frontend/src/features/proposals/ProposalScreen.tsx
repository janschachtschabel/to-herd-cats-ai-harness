import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { DiffLines } from '@/features/wiki/versions/DiffLines'
import { useWiki } from '@/features/wiki/WikiContext'
import { formatDateTime } from '@/lib/format'
import { proposalTitle } from './display'
import { outdatedOf } from './merge'
import { ProposalActions } from './ProposalActions'
import { ProposalAuthor } from './ProposalAuthor'
import { ProposalOutcome } from './ProposalOutcome'
import { useProposal } from './queries'
import { RunNote } from './RunNote'

/** One proposal: what it changes (the diff from its base, insertions and deletions
 *  marked), who proposed it and why, the run it came from when the reader may see
 *  it, and for moderators accept (with the merge dialog when the page moved on) and
 *  reject. */
export function ProposalScreen({ proposalId }: { proposalId: string }) {
  const { t, i18n } = useTranslation()
  const { space, nodes, abilities } = useWiki()
  const proposal = useProposal(proposalId)

  if (proposal.isPending) return <LoadingState />
  if (proposal.isError) {
    return <ErrorState error={proposal.error} onRetry={() => void proposal.refetch()} />
  }
  const data = proposal.data
  const outdated = outdatedOf(data)

  return (
    <article aria-labelledby="proposal-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="proposal-title" className="text-xl font-semibold tracking-tight break-words">
            {proposalTitle(t, data, nodes)}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant={data.state === 'open' ? 'default' : 'secondary'}>
              {t(`proposals.states.${data.state}`)}
            </Badge>
            <ProposalAuthor proposal={data} />
            <span>{formatDateTime(data.created_at, i18n.language)}</span>
          </div>
        </div>
        <Button variant="outline" asChild>
          <Link to="/spaces/$spaceId/proposals" params={{ spaceId: space.id }}>
            <ArrowLeft aria-hidden />
            {t('proposals.back')}
          </Link>
        </Button>
      </div>
      <section aria-labelledby="proposal-reason" className="rounded-lg border p-3 text-sm">
        <h3 id="proposal-reason" className="mb-1 text-xs font-medium text-muted-foreground">
          {t('proposals.reason')}
        </h3>
        <p>{data.reason}</p>
        {data.run_id && <RunNote runId={data.run_id} />}
      </section>
      <ProposalOutcome proposal={data} />
      {outdated && (
        <Alert>
          <AlertDescription>{t('proposals.outdated')}</AlertDescription>
        </Alert>
      )}
      {abilities.moderate && data.state === 'open' && (
        <ProposalActions proposal={data} outdated={outdated} />
      )}
      <section aria-label={t('proposals.diffLabel')} className="flex flex-col gap-2">
        {data.too_large || data.diff === null ? (
          <p className="text-sm text-muted-foreground">{t('proposals.tooLarge')}</p>
        ) : data.diff.every((h) => h.kind === 'equal') ? (
          <p className="text-sm text-muted-foreground">{t('proposals.noChange')}</p>
        ) : (
          <DiffLines hunks={data.diff} />
        )}
      </section>
    </article>
  )
}
