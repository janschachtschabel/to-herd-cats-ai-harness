import { RunWaiting } from '@/features/approvals/RunWaiting'
import { useRun } from '@/features/agents/queries'
import { RunPage } from './RunPage'

/** The run page as the router shows it, with the release cards at its waiting calls. */
export function RunScreen({ runId }: { runId: string }) {
  const run = useRun(runId)
  return (
    <RunPage
      runId={runId}
      waiting={(item) => (
        <RunWaiting
          runId={runId}
          step={item.step}
          call={item.call}
          askerName={run.data?.asker_name ?? ''}
        />
      )}
    />
  )
}
