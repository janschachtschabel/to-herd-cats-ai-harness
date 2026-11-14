import { RunPage } from './RunPage'

/** The run page as the router shows it. */
export function RunScreen({ runId }: { runId: string }) {
  return <RunPage runId={runId} />
}
