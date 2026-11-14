import { Link } from '@tanstack/react-router'
import { CalendarClock, PauseCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { RunLink } from '@/features/runs/RunBits'
import { stateText as runStateText } from '@/features/runs/display'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import {
  agentName,
  excerpt,
  outcomeText,
  placeText,
  scheduleText,
  stateText,
  termText,
} from './display'
import type { Automation } from './queries'

/** How its latest term went: the outcome and, for a run, how the run stands. */
export function LastRun({ automation }: { automation: Automation }) {
  const { t } = useTranslation()
  const last = automation.last_run
  if (!last) return <span>{t('automations.list.noRun')}</span>
  const run = last.run_state ? { state: last.run_state, stop_reason: last.stop_reason } : null
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2">
      <span>
        {outcomeText(t, last)}
        {run && !last.heartbeat_ok && ` · ${runStateText(t, run)}`}
      </span>
      {last.run_id && <RunLink runId={last.run_id} label={t('automations.list.openRun')} />}
    </span>
  )
}

/** The next term in my time (the automation's zone named where it differs). */
export function NextTerm({ automation }: { automation: Automation }) {
  const { t, i18n } = useTranslation()
  if (automation.kind === 'event') return <span>{t('automations.list.onEvent')}</span>
  if (!automation.next_due_at) return <span>{t('automations.list.noNext')}</span>
  return (
    <time dateTime={automation.next_due_at}>
      {termText(t, automation.next_due_at, i18n.language, automation.time_zone, true)}
    </time>
  )
}

function AutomationRow({ automation, showOwner }: { automation: Automation; showOwner: boolean }) {
  const { t, i18n } = useTranslation()
  const paused = automation.state === 'paused'
  return (
    <li
      className="rounded-lg border p-3 focus-within:ring-2 focus-within:ring-ring/50"
      data-testid="automation-row"
    >
      <div className="flex flex-wrap items-center gap-2">
        <CalendarClock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <Link
          to="/automations/$automationId"
          params={{ automationId: automation.id }}
          className="min-w-0 font-medium break-words underline-offset-2 hover:underline focus-visible:outline-none"
        >
          {excerpt(automation.instruction)}
        </Link>
        <Badge variant="outline">{t(`automations.kinds.${automation.kind}`)}</Badge>
        {!paused && <Badge variant="secondary">{stateText(t, automation)}</Badge>}
      </div>
      {paused && (
        <p className="mt-1 flex items-start gap-1.5 text-sm text-amber-800 dark:text-amber-200">
          <PauseCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{stateText(t, automation)}</span>
        </p>
      )}
      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-muted-foreground">
        <span>{scheduleText(t, automation, i18n.language)}</span>
        <span aria-hidden>·</span>
        <span className="inline-flex items-center gap-1">
          {agentName(t, automation)} <AgentBadge of="agent" />
        </span>
        <span aria-hidden>·</span>
        <span>{placeText(t, automation)}</span>
        {showOwner && (
          <>
            <span aria-hidden>·</span>
            <span>
              {t('automations.list.owner', {
                name: automation.owner.name ?? t('automations.list.unknownOwner'),
              })}
            </span>
          </>
        )}
      </p>
      <dl className="mt-2 grid gap-x-4 gap-y-0.5 text-xs sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">{t('automations.list.next')}</dt>
        <dd>
          <NextTerm automation={automation} />
        </dd>
        <dt className="text-muted-foreground">{t('automations.list.lastRun')}</dt>
        <dd>
          <LastRun automation={automation} />
        </dd>
      </dl>
    </li>
  )
}

export interface AutomationListData {
  items: Automation[]
  isPending: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
  hasMore: boolean
  loadingMore: boolean
  loadMore: () => void
}

/** A paged list of automations with its loading, empty and error states. */
export function AutomationList({
  list,
  emptyText,
  showOwner = false,
}: {
  list: AutomationListData
  emptyText: string
  showOwner?: boolean
}) {
  const { t } = useTranslation()
  if (list.isPending) return <LoadingState />
  if (list.isError) return <ErrorState error={list.error} onRetry={() => void list.refetch()} />
  if (list.items.length === 0) return <EmptyState text={emptyText} />
  return (
    <>
      <ul className="flex flex-col gap-2" aria-label={t('automations.list.label')}>
        {list.items.map((automation) => (
          <AutomationRow key={automation.id} automation={automation} showOwner={showOwner} />
        ))}
      </ul>
      <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
    </>
  )
}
