import { useTranslation } from 'react-i18next'
import { RunLink } from '@/features/runs/RunBits'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { outcomeText } from './display'
import { useFirings } from './queries'

/** The log of its terms, newest first: when each was due, how it went, its run. */
export function FiringLog({ automationId }: { automationId: string }) {
  const { t, i18n } = useTranslation()
  const log = useFirings(automationId)
  let body
  if (log.isPending) body = <LoadingState rows={3} />
  else if (log.isError) body = <ErrorState error={log.error} onRetry={() => void log.refetch()} />
  else if (log.items.length === 0) body = <EmptyState text={t('automations.detail.logEmpty')} />
  else
    body = (
      <>
        <ul className="divide-y rounded-lg border" aria-label={t('automations.detail.logLabel')}>
          {log.items.map((firing) => (
            <li
              key={firing.id}
              className="flex flex-col gap-1 px-3 py-2 text-sm sm:flex-row sm:items-center sm:gap-4"
              data-testid="firing-row"
              data-outcome={firing.outcome}
            >
              <time
                dateTime={firing.due_at}
                className="shrink-0 text-muted-foreground tabular-nums"
              >
                {formatDateTime(firing.due_at, i18n.language)}
              </time>
              <span
                className={cn(
                  'min-w-0 flex-1',
                  firing.outcome !== 'started' && 'text-amber-800 dark:text-amber-200',
                )}
              >
                {outcomeText(t, firing)}
              </span>
              {firing.run_id && (
                <RunLink runId={firing.run_id} label={t('automations.list.openRun')} />
              )}
            </li>
          ))}
        </ul>
        <LoadMore hasMore={log.hasMore} loading={log.loadingMore} onLoad={log.loadMore} />
      </>
    )
  return (
    <section aria-labelledby="automation-log" className="flex flex-col gap-3">
      <h2 id="automation-log" className="text-base font-semibold">
        {t('automations.detail.log')}
      </h2>
      {body}
    </section>
  )
}
