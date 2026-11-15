import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { RunNote } from '@/features/proposals/RunNote'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { spaceQuery } from '@/features/spaces/queries'
import { formatDateTime } from '@/lib/format'
import { skillAbilities } from '../abilities'
import { SkillAuthor } from '../SkillAuthor'
import { skillProposalTitle, skillProposalWhere } from './display'
import { useSkillProposal } from './queries'
import { SkillProposalActions } from './SkillProposalActions'
import { SkillProposalOutcome } from './SkillProposalOutcome'
import { SkillProposalText } from './SkillProposalText'

/** One proposal for a skill: what it changes (the skill now against the proposal) or
 *  the new skill's text, who proposed it (an agent carries the AI mark) and why, the
 *  run it came from for those who may read it, and for those who may decide accept
 *  (with the dialog when the skill moved on) and reject. */
export function SkillProposalScreen({ proposalId }: { proposalId: string }) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const proposal = useSkillProposal(proposalId)
  const spaceId = proposal.data?.space_id ?? null
  const space = useQuery({ ...spaceQuery(spaceId ?? ''), enabled: spaceId !== null })

  if (proposal.isPending) return <LoadingState />
  if (proposal.isError) {
    return <ErrorState error={proposal.error} onRetry={() => void proposal.refetch()} />
  }
  const data = proposal.data
  const decides =
    skillAbilities(me, spaceId ? (space.data ?? null) : null).manage &&
    (spaceId === null || space.data !== undefined)
  const names = space.data ? new Map([[space.data.id, space.data.name]]) : undefined

  return (
    <article aria-labelledby="skill-proposal-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1
            id="skill-proposal-title"
            className="text-xl font-semibold tracking-tight break-words"
          >
            {skillProposalTitle(t, data)}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant={data.state === 'open' ? 'default' : 'secondary'}>
              {t(`proposals.states.${data.state}`)}
            </Badge>
            <Badge variant="outline">{skillProposalWhere(t, data, names)}</Badge>
            <SkillAuthor author={data.author} />
            <span>{formatDateTime(data.created_at, i18n.language)}</span>
          </div>
        </div>
        <Button variant="outline" asChild>
          {spaceId ? (
            <Link to="/spaces/$spaceId/skills" params={{ spaceId }} search={{ view: 'proposals' }}>
              <ArrowLeft aria-hidden />
              {t('skills.proposals.back')}
            </Link>
          ) : (
            <Link to="/admin/skills" search={{ view: 'proposals' }}>
              <ArrowLeft aria-hidden />
              {t('skills.proposals.back')}
            </Link>
          )}
        </Button>
      </div>
      <section aria-labelledby="skill-proposal-reason" className="rounded-lg border p-3 text-sm">
        <h2 id="skill-proposal-reason" className="mb-1 text-xs font-medium text-muted-foreground">
          {t('proposals.reason')}
        </h2>
        <p className="break-words">{data.reason}</p>
        {data.run_id && <RunNote runId={data.run_id} />}
      </section>
      <SkillProposalOutcome proposal={data} />
      {data.outdated && data.state === 'open' && (
        <Alert>
          <AlertDescription>{t('skills.proposals.outdated')}</AlertDescription>
        </Alert>
      )}
      {decides && data.state === 'open' && <SkillProposalActions proposal={data} />}
      <SkillProposalText proposal={data} />
    </article>
  )
}
