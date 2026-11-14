/** The query keys of agents. Runs share the prefix `['agents', 'run']`, so a new
 *  message can refresh every run shown at once. */
export const agentKeys = {
  all: ['agents'] as const,
  list: ['agents', 'list'] as const,
  detail: (id: string) => ['agents', 'detail', id] as const,
  profile: (id: string) => ['agents', 'profile', id] as const,
  runs: ['agents', 'run'] as const,
  run: (id: string) => ['agents', 'run', id] as const,
  runEvents: (id: string) => ['agents', 'run-events', id] as const,
  /** Every run's steps (refreshed with the runs when something happened). */
  allRunEvents: ['agents', 'run-events'] as const,
  /** The run of a direct message the page knows about: never fetched, only set (from
   *  the answer to sending, and from `run.progress`). */
  activeRun: (conversationId: string) => ['agents', 'active-run', conversationId] as const,
}

export interface ActiveRun {
  runId: string
  step: number | null
}
