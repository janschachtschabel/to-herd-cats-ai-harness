import { Link } from '@tanstack/react-router'
import { Activity } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useRun, type Run } from '@/features/agents/queries'
import { useMe } from '@/features/auth/queries'
import { cn } from '@/lib/utils'
import { readsRuns, stateText, stateTone } from './display'

const TONES = {
  active:
    'border-violet-300 bg-violet-50 text-violet-900 dark:border-violet-500/40 dark:bg-violet-500/15 dark:text-violet-100',
  ok: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-100',
  stopped:
    'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-100',
} as const

/** A run's state as a small badge (its words carry the meaning, not its colour). */
export function RunStateBadge({ run }: { run: Pick<Run, 'state' | 'stop_reason'> }) {
  const { t } = useTranslation()
  return (
    <span
      data-run-state={run.state}
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        TONES[stateTone(run)],
      )}
    >
      {stateText(t, run)}
    </span>
  )
}

/** A link to a run's page ("Lauf ansehen"), for those the API showed the run to. */
export function RunLink({
  runId,
  className,
  label,
}: {
  runId: string
  className?: string
  label?: string
}) {
  const { t } = useTranslation()
  return (
    <Link
      to="/runs/$runId"
      params={{ runId }}
      className={cn(
        'inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline',
        className,
      )}
    >
      <Activity className="size-3.5" aria-hidden />
      {label ?? t('runs.link')}
    </Link>
  )
}

/** A link to a run only for those the API shows the run to: it asks for the run (if
 *  the reader may read runs at all) and links once it is there; a 404 shows nothing. */
export function VisibleRunLink({ runId, className }: { runId: string; className?: string }) {
  const me = useMe()
  const run = useRun(readsRuns(me) ? runId : null)
  if (!run.data) return null
  return <RunLink runId={runId} className={className} />
}
