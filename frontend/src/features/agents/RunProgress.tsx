import { Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useActiveRun, useRun } from './queries'

/** While the agent of a direct message works: a card with its step. It follows the
 *  run this page heard of (sending, `run.progress`) and vanishes once the run is done;
 *  its answer or stop notice then stands in the conversation. */
export function RunProgress({
  conversationId,
  agentName,
}: {
  conversationId: string
  agentName: string
}) {
  const { t } = useTranslation()
  const active = useActiveRun(conversationId)
  const run = useRun(active?.runId ?? null)
  if (!active || !run.data || run.data.state === 'done') return null
  const step = Math.max(run.data.steps, active.step ?? 0)
  return (
    <div
      role="status"
      data-run-state={run.data.state}
      className="mx-1 mb-2 flex items-center gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-100"
    >
      <Loader2 className="size-4 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden />
      <span>
        {run.data.state === 'queued'
          ? t('agents.progress.queued', { name: agentName })
          : t('agents.progress.working', { name: agentName, count: step })}
      </span>
    </div>
  )
}
