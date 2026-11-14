import { Hourglass, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { RunLink } from '@/features/runs/RunBits'
import { useActiveRun, useRun } from './queries'

/** Where the card stands: in a direct message with the agent, under a channel's (or a
 *  page's or ticket's thread's) messages while the run answers in a message's thread,
 *  or in that thread. */
export type ProgressPlace =
  | { kind: 'dm' }
  | { kind: 'conversation'; onOpenThread?: (threadId: string) => void }
  | { kind: 'thread'; threadId: string }

/** While an agent works on what this page asked or heard of: a card with its step (or
 *  that it waits for a release or an answer) and a link to the run. It follows the run
 *  this page heard of (sending, `run.progress`) and vanishes once the run is done; its
 *  answer or stop notice then stands in the conversation. Shown only to those the API
 *  shows the run to (everyone else gets 404 and sees nothing). */
export function RunProgress({
  conversationId,
  place,
}: {
  conversationId: string
  place: ProgressPlace
}) {
  const { t } = useTranslation()
  const active = useActiveRun(conversationId)
  const run = useRun(active?.runId ?? null)
  if (!active || !run.data || run.data.state === 'done') return null
  const threadId = active.threadId ?? run.data.trigger_message_id ?? null
  if (place.kind === 'thread' && threadId !== place.threadId) return null
  const name = run.data.agent_name
  // Steps done so far; the card names the one in progress.
  const step = Math.max(run.data.steps, active.step ?? 0) + 1
  const where = place.kind === 'conversation' ? 'Thread' : ''
  const text =
    run.data.state === 'queued'
      ? t(`agents.progress.queued${where}`, { name })
      : run.data.state === 'waiting'
        ? t('agents.progress.waiting', { name })
        : t(`agents.progress.working${where}`, { name, count: step })
  const openThread = place.kind === 'conversation' ? place.onOpenThread : undefined
  return (
    <div
      role="status"
      aria-label={t('agents.progress.label', { name })}
      data-run-state={run.data.state}
      className="mx-1 mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-100"
    >
      {run.data.state === 'waiting' ? (
        <Hourglass className="size-4 shrink-0" aria-hidden />
      ) : (
        <Loader2 className="size-4 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden />
      )}
      <span className="min-w-0 flex-1">{text}</span>
      {openThread && threadId && (
        <Button variant="link" size="xs" className="px-0" onClick={() => openThread(threadId)}>
          {t('agents.progress.openThread')}
        </Button>
      )}
      <RunLink runId={active.runId} />
    </div>
  )
}
