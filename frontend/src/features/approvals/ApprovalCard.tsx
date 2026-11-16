import { ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useRun } from '@/features/agents/queries'
import { useMe } from '@/features/auth/queries'
import { RunLink } from '@/features/runs/RunBits'
import { toolText } from '@/features/runs/display'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { formatDateTime } from '@/lib/format'
import { useNow } from '@/lib/useNow'
import { ApprovalDecision } from './ApprovalDecision'
import { ApprovalSubject } from './ApprovalSubject'
import { useReleasable } from './releasable'
import { CardFrame, CardState, type Tone } from './CardFrame'
import { approvalView, externalToolOf, mayDecide, type ApprovalView } from './display'
import { useApproval, useDecideApproval, type Approval } from './queries'

const TONE: Record<ApprovalView, Tone> = {
  pending: 'waiting',
  approved: 'ok',
  done: 'ok',
  stale: 'off',
  failed: 'off',
  rejected: 'off',
  expired: 'off',
}

/** Who decides: "you", or the person who asked the run (by name, from the run). */
function Decider({ approval, meId }: { approval: Approval; meId: string | undefined }) {
  const { t } = useTranslation()
  const run = useRun(approval.addressed_to === meId ? null : approval.run_id)
  if (approval.addressed_to === meId) return <>{t('approvals.card.youDecide')}</>
  return (
    <>
      {run.data
        ? t('approvals.card.decides', { name: run.data.asker_name })
        : t('approvals.card.askerDecides')}
    </>
  )
}

/** A release card that the API showed: what the agent wants to do (the tool in words,
 *  the server's summary, links to what it would change, the diff; for an external
 *  tool "server · tool" and, for the person asked, the exact arguments), who decides, its
 *  state (waiting, approved and run, stale because the object changed, rejected with
 *  its reason, expired), the decision for the person asked, and a link to the run.
 *  A rejection's reason is the asked person's to read (others: `redacted`). Under the
 *  personal mark (`personal`) it says so: she releases exactly what is shown. */
export function ApprovalCardView({ approval }: { approval: Approval }) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const meId = me?.user.id
  const now = useNow(60_000)
  const decide = useDecideApproval(approval.id)
  // After an approval the API tells whether the call ran or was stale.
  const view = approvalView(approval, now)
  const when = (iso: string | null) => (iso ? formatDateTime(iso, i18n.language) : '')
  const external = externalToolOf(approval)
  const releasable = useReleasable(approval)
  return (
    <CardFrame
      icon={<ShieldCheck className="size-4" />}
      label={t('approvals.card.label')}
      title={
        external !== null
          ? t('approvals.card.titleExternal', { tool: external })
          : t('approvals.card.title', { tool: toolText(t, approval.tool) })
      }
      state={<CardState tone={TONE[view]}>{t(`approvals.state.${view}`)}</CardState>}
    >
      {approval.summary !== null ? (
        <p
          className={
            external !== null
              ? 'text-sm font-medium break-words'
              : 'font-mono text-xs break-words text-muted-foreground'
          }
        >
          {approval.summary}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">{t('approvals.card.summaryRedacted')}</p>
      )}
      {approval.personal && (
        <p className="rounded-md border border-sky-300 bg-sky-50 px-2 py-1 text-xs text-sky-900 dark:border-sky-500/40 dark:bg-sky-500/15 dark:text-sky-100">
          {t('approvals.card.personal')}
        </p>
      )}
      <ApprovalSubject approval={approval} />
      {view === 'pending' ? (
        <p className="text-xs text-muted-foreground">
          <Decider approval={approval} meId={meId} />{' '}
          {t('approvals.card.until', { when: when(approval.expires_at) })}
        </p>
      ) : (
        <p className="text-xs">
          {t(`approvals.outcome.${view}`, { when: when(approval.decided_at) })}
          {view === 'rejected' && approval.reason && (
            <span className="mt-0.5 block text-muted-foreground">
              {t('approvals.card.reason', { reason: approval.reason })}
            </span>
          )}
          {view === 'rejected' && approval.redacted && (
            <span className="mt-0.5 block text-muted-foreground">
              {t('approvals.card.reasonRedacted')}
            </span>
          )}
        </p>
      )}
      {mayDecide(approval, meId, now) && (
        <ApprovalDecision approval={approval} decide={decide} releasable={releasable} />
      )}
      {decide.isError && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, decide.error)}
        </p>
      )}
      <RunLink runId={approval.run_id} />
    </CardFrame>
  )
}

/** A release card by id (a message's card). Someone who may not see it (the API
 *  answers 404) sees the tool the message names and that only the person asked
 *  decides. */
export function ApprovalCard({ approvalId, tool }: { approvalId: string; tool: string }) {
  const { t } = useTranslation()
  const approval = useApproval(approvalId)
  if (approval.isPending) {
    return <p className="mt-1 text-xs text-muted-foreground">{t('states.loading')}</p>
  }
  if (approval.data) return <ApprovalCardView approval={approval.data} />
  const hidden = approval.error instanceof ApiError && approval.error.status === 404
  return (
    <CardFrame
      icon={<ShieldCheck className="size-4" />}
      label={t('approvals.card.label')}
      title={t('approvals.card.titleUnknown')}
    >
      <p className="text-xs break-words text-muted-foreground">{toolText(t, tool)}</p>
      {hidden ? (
        <p className="text-xs text-muted-foreground">{t('approvals.card.notYours')}</p>
      ) : (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, approval.error)}
        </p>
      )}
    </CardFrame>
  )
}
