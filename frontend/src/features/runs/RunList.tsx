import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { STOP_REASONS_ALL, stopText } from '@/features/agents/display'
import type { Run } from '@/features/agents/queries'
import { formatCost } from '@/features/ai/usage/period'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { useNow } from '@/lib/useNow'
import { durationMs, formatDuration, placeText, RUN_STATES } from './display'
import type { RunFilters } from './queries'
import { RunStateBadge } from './RunBits'

/** The filters of a run list: its state and why it stopped (each change goes into the
 *  address through `onChange`). */
export function RunFilterBar({
  filters,
  onChange,
}: {
  filters: RunFilters
  onChange: (next: RunFilters) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      <label className="flex min-w-40 flex-1 flex-col gap-1 text-xs text-muted-foreground sm:flex-none">
        {t('runs.filters.state')}
        <NativeSelect
          value={filters.state ?? ''}
          onChange={(e) =>
            onChange({ ...filters, state: (e.target.value || undefined) as RunFilters['state'] })
          }
        >
          <option value="">{t('runs.filters.all')}</option>
          {RUN_STATES.map((state) => (
            <option key={state} value={state}>
              {t(`runs.states.${state}`)}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label className="flex min-w-40 flex-1 flex-col gap-1 text-xs text-muted-foreground sm:flex-none">
        {t('runs.filters.stopReason')}
        <NativeSelect
          value={filters.stop_reason ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              stop_reason: (e.target.value || undefined) as RunFilters['stop_reason'],
            })
          }
        >
          <option value="">{t('runs.filters.all')}</option>
          {STOP_REASONS_ALL.map((reason) => (
            <option key={reason} value={reason}>
              {t(`runs.stopReasons.${reason}`)}
            </option>
          ))}
        </NativeSelect>
      </label>
    </div>
  )
}

/** One run in a list: agent, state, where, when, how long and what it cost. */
function RunRow({ run, showAgent, now }: { run: Run; showAgent: boolean; now: number }) {
  const { t, i18n } = useTranslation()
  const cost = formatCost(run.usage.cost, i18n.language)
  return (
    <li className="rounded-lg border p-3 focus-within:ring-2 focus-within:ring-ring/50">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to="/runs/$runId"
          params={{ runId: run.id }}
          className="font-medium underline-offset-2 hover:underline focus-visible:outline-none"
        >
          {showAgent
            ? t('runs.list.title', { agent: run.agent_name, place: placeText(t, run) })
            : t('runs.list.titleNoAgent', { place: placeText(t, run), asker: run.asker_name })}
        </Link>
        {showAgent && <AgentBadge />}
        <RunStateBadge run={run} />
      </div>
      {run.state === 'done' && run.stop_reason !== 'completed' && (
        <p className="mt-1 text-sm text-muted-foreground">{stopText(t, run.stop_reason)}</p>
      )}
      <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <time dateTime={run.created_at}>{formatDateTime(run.created_at, i18n.language)}</time>
        <span>{formatDuration(t, durationMs(run, now))}</span>
        <span>{t('runs.list.steps', { count: run.steps })}</span>
        {cost !== null && <span>{t('runs.list.cost', { cost })}</span>}
      </p>
    </li>
  )
}

/** A paged list of runs with its loading, empty and error states. */
export function RunList({
  list,
  showAgent,
  emptyText,
}: {
  list: {
    items: Run[]
    isPending: boolean
    isError: boolean
    error: unknown
    refetch: () => unknown
    hasMore: boolean
    loadingMore: boolean
    loadMore: () => void
  }
  showAgent: boolean
  emptyText: string
}) {
  const { t } = useTranslation()
  const now = useNow()
  if (list.isPending) return <LoadingState />
  if (list.isError) return <ErrorState error={list.error} onRetry={() => void list.refetch()} />
  if (list.items.length === 0) return <EmptyState text={emptyText} />
  return (
    <>
      <ul className="flex flex-col gap-2" aria-label={t('runs.list.label')}>
        {list.items.map((run) => (
          <RunRow key={run.id} run={run} showAgent={showAgent} now={now} />
        ))}
      </ul>
      <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
    </>
  )
}
