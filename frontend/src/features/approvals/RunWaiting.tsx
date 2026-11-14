import { useTranslation } from 'react-i18next'
import type { AskedCall } from '@/features/runs/timeline'
import { ApprovalCardView } from './ApprovalCard'
import { useMyApprovals } from './queries'

/** At a run's call that waits: the release card for the person asked (from my open
 *  releases, the one of this run, step and call), the question as the agent asked it,
 *  or whose decision it waits for. */
export function RunWaiting({
  runId,
  step,
  call,
  askerName,
}: {
  runId: string
  step: number
  call: AskedCall
  askerName: string
}) {
  const { t } = useTranslation()
  const mine = useMyApprovals('pending')
  if (call.name === 'ask_user') {
    const asked = (call.args as { question?: unknown } | null)?.question
    return (
      <div className="mt-1 flex flex-col gap-1 text-sm">
        {typeof asked === 'string' && <p className="whitespace-pre-wrap">{asked}</p>}
        <p className="text-xs text-muted-foreground">
          {t('approvals.waiting.question', { name: askerName })}
        </p>
      </div>
    )
  }
  const approval = mine.items.find(
    (a) => a.run_id === runId && a.step === step && a.call_id === call.id,
  )
  if (approval) return <ApprovalCardView approval={approval} />
  return (
    <p className="mt-1 text-xs text-muted-foreground">
      {t('approvals.waiting.approval', { name: askerName })}
    </p>
  )
}
