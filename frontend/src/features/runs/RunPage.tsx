import { Link } from '@tanstack/react-router'
import { ArrowLeft, Square } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useRun } from '@/features/agents/queries'
import { useMe } from '@/features/auth/queries'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { useNow } from '@/lib/useNow'
import { mayCancel } from './display'
import { useCancelRun } from './queries'
import { RunHeader } from './RunHeader'
import { RunTimeline } from './RunTimeline'
import type { TimelineItem } from './timeline'

type Waiting = Extract<TimelineItem, { kind: 'waiting' }>

function CancelRun({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const cancel = useCancelRun(runId)
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Square aria-hidden />
        {t('runs.cancel.open')}
      </Button>
      <ConfirmDialog
        open={open}
        title={t('runs.cancel.title')}
        text={t('runs.cancel.text')}
        confirmLabel={t('runs.cancel.confirm')}
        destructive
        pending={cancel.isPending}
        error={cancel.error}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) cancel.reset()
        }}
        onConfirm={() => cancel.mutate(undefined, { onSuccess: () => setOpen(false) })}
      />
    </>
  )
}

/**
 * One run, for those the API shows it to: what it is (header), its steps (timeline),
 * and a stop with confirmation while it may still be stopped. It follows the run live
 * through the events that refresh it (`run.progress`, new messages, decided cards).
 */
export function RunPage({
  runId,
  waiting = () => null,
}: {
  runId: string
  /** What stands at a call that waits (the release card, for the person asked). */
  waiting?: (item: Waiting, runId: string) => ReactNode
}) {
  const { t } = useTranslation()
  const me = useMe()
  const run = useRun(runId)
  const now = useNow(run.data && run.data.state !== 'done' ? 1000 : null)
  if (run.isPending) return <LoadingState />
  if (run.isError) return <ErrorState error={run.error} onRetry={() => void run.refetch()} />
  const data = run.data
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t('runs.page.title', { name: data.agent_name })}
        description={
          data.cancel_requested && data.state !== 'done' ? t('runs.cancel.requested') : undefined
        }
        actions={
          <>
            <Button variant="ghost" asChild>
              <Link to="/runs">
                <ArrowLeft aria-hidden />
                {t('runs.page.back')}
              </Link>
            </Button>
            {mayCancel(data) && <CancelRun runId={runId} />}
          </>
        }
      />
      <RunHeader run={data} meId={me?.user.id} now={now} />
      <section aria-labelledby="run-steps">
        <h2 id="run-steps" className="mb-3 text-sm font-semibold">
          {t('runs.timeline.title')}
        </h2>
        <RunTimeline run={data} waiting={(item) => waiting(item, runId)} />
      </section>
    </div>
  )
}
