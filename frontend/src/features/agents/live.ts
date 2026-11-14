import type { QueryClient } from '@tanstack/react-query'
import type { LiveEvent } from '@/lib/live'
import { agentKeys, type ActiveRun } from './keys'
import { setActiveRun } from './queries'

/** `run.progress` names a conversation's run and its step: the page follows that run
 *  (its card refetches the run itself; the event carries ids only). The thread it
 *  answers in stays as known from sending. */
export function noteRunProgress(queryClient: QueryClient, event: LiveEvent): void {
  if (event.type !== 'run.progress' || !event.conversationId || !event.runId) return
  const known = queryClient.getQueryData<ActiveRun>(agentKeys.activeRun(event.conversationId))
  const threadId = known?.runId === event.runId ? known.threadId : undefined
  setActiveRun(queryClient, event.conversationId, {
    runId: event.runId,
    step: event.step ?? null,
    threadId,
  })
}
