import type { QueryClient } from '@tanstack/react-query'
import type { LiveEvent } from '@/lib/live'
import { setActiveRun } from './queries'

/** `run.progress` names the run of a direct message and its step: the page follows
 *  that run (its card refetches the run itself; the event carries ids only). */
export function noteRunProgress(queryClient: QueryClient, event: LiveEvent): void {
  if (event.type !== 'run.progress' || !event.conversationId || !event.runId) return
  setActiveRun(queryClient, event.conversationId, { runId: event.runId, step: event.step ?? null })
}
