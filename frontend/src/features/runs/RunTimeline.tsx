import { Bot, CircleStop, EyeOff, Hourglass, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { stopText } from '@/features/agents/display'
import type { Run } from '@/features/agents/queries'
import { formatCost } from '@/features/ai/usage/period'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDuration, toolText } from './display'
import { useRunTimeline } from './queries'
import { approvalOutcome, buildTimeline, readable, type TimelineItem } from './timeline'

/** Something folded away: arguments and results, readable when opened. */
function Folded({ summary, body }: { summary: string; body: string }) {
  if (!body) return null
  return (
    <details className="mt-1 rounded-md border bg-muted/30 text-xs">
      <summary className="cursor-pointer px-2 py-1 font-medium select-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none">
        {summary}
      </summary>
      <pre className="max-h-96 overflow-auto px-2 pb-2 font-mono text-xs break-words whitespace-pre-wrap">
        {body}
      </pre>
    </details>
  )
}

function Hidden() {
  const { t } = useTranslation()
  return (
    <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <EyeOff className="size-3.5" aria-hidden />
      {t('runs.timeline.hidden')}
    </p>
  )
}

function Row({
  icon,
  title,
  meta,
  children,
}: {
  icon: ReactNode
  title: ReactNode
  meta?: string
  children?: ReactNode
}) {
  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      <span
        aria-hidden
        className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border bg-background text-muted-foreground"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title}</p>
        {meta && <p className="text-xs text-muted-foreground">{meta}</p>}
        {children}
      </div>
    </li>
  )
}

function ModelStep({ item }: { item: Extract<TimelineItem, { kind: 'model' }> }) {
  const { t, i18n } = useTranslation()
  const e = item.event
  const meta = [
    e.tokens_in !== null &&
      t('runs.timeline.tokens', { tokensIn: e.tokens_in, tokensOut: e.tokens_out ?? 0 }),
    e.duration_ms !== null && formatDuration(t, e.duration_ms),
    e.cost !== null && formatCost(e.cost, i18n.language),
  ].filter(Boolean)
  return (
    <Row
      icon={<Bot className="size-3.5" />}
      title={t('runs.timeline.model', { step: item.step })}
      meta={meta.join(' · ')}
    >
      {e.redacted ? (
        <Hidden />
      ) : (
        item.text && <p className="mt-1 text-sm whitespace-pre-wrap">{item.text}</p>
      )}
      {item.calls.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          {t('runs.timeline.calls', {
            tools: item.calls.map((c) => toolText(t, c.name)).join(', '),
          })}
        </p>
      )}
    </Row>
  )
}

function ToolStep({ item }: { item: Extract<TimelineItem, { kind: 'tool' }> }) {
  const { t } = useTranslation()
  const outcome = item.source === 'approval' ? approvalOutcome(item.result) : null
  const e = item.event
  return (
    <Row
      icon={<Wrench className="size-3.5" />}
      title={toolText(t, item.name)}
      meta={e.duration_ms !== null ? formatDuration(t, e.duration_ms) : undefined}
    >
      {outcome && (
        <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
          {t(`runs.timeline.approval.${outcome}`)}
        </p>
      )}
      {item.final && <p className="mt-1 text-sm">{t('runs.timeline.final')}</p>}
      {e.redacted ? (
        <Hidden />
      ) : (
        <>
          <Folded summary={t('runs.timeline.args')} body={readable(item.args)} />
          <Folded summary={t('runs.timeline.result')} body={item.result ?? ''} />
        </>
      )}
    </Row>
  )
}

/**
 * A run's steps as a timeline: each model step (its words, tokens, duration, the tools
 * it called), each tool call with arguments and result folded, calls waiting for a
 * release or an answer (`waiting`, rendered by the caller), and the stop. What the
 * reader may not see is named as hidden.
 */
export function RunTimeline({
  run,
  waiting,
}: {
  run: Run
  waiting: (item: Extract<TimelineItem, { kind: 'waiting' }>) => ReactNode
}) {
  const { t } = useTranslation()
  const events = useRunTimeline(run.id)
  if (events.isPending) return <LoadingState rows={3} />
  if (events.isError) {
    return <ErrorState error={events.error} onRetry={() => void events.refetch()} />
  }
  const items = buildTimeline(events.items, run)
  if (items.length === 0) return <EmptyState text={t('runs.timeline.empty')} />
  return (
    <>
      <ol aria-label={t('runs.timeline.label')} className="flex flex-col">
        {items.map((item) =>
          item.kind === 'model' ? (
            <ModelStep key={item.key} item={item} />
          ) : item.kind === 'tool' ? (
            <ToolStep key={item.key} item={item} />
          ) : item.kind === 'waiting' ? (
            <Row
              key={item.key}
              icon={<Hourglass className="size-3.5" />}
              title={
                item.call.name === 'ask_user'
                  ? t('runs.timeline.waitingAnswer')
                  : t('runs.timeline.waitingApproval', { tool: toolText(t, item.call.name) })
              }
            >
              {waiting(item)}
            </Row>
          ) : (
            <Row
              key={item.key}
              icon={<CircleStop className="size-3.5" />}
              title={t('runs.timeline.stop')}
            >
              <p className="mt-1 text-sm">{stopText(t, item.reason)}</p>
            </Row>
          ),
        )}
      </ol>
      <LoadMore hasMore={events.hasMore} loading={events.loadingMore} onLoad={events.loadMore} />
    </>
  )
}
