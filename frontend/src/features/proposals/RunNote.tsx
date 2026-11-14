import { useTranslation } from 'react-i18next'
import { useRun } from '@/features/agents/queries'
import { RunLink } from '@/features/runs/RunBits'

/** The run a proposal came from, for those who may read the run (the person who
 *  started it, the agent's responsible person, agent admins); others learn nothing
 *  (the API answers 404 and nothing is shown). */
export function RunNote({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const run = useRun(runId)
  if (!run.data) return null
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
      {t('proposals.run', {
        state: t(`proposals.runStates.${run.data.state}`),
        count: run.data.steps,
      })}
      <RunLink runId={runId} className="text-foreground" />
    </p>
  )
}
