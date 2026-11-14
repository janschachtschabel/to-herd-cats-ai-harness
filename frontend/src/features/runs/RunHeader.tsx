import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { stopText } from '@/features/agents/display'
import type { Run } from '@/features/agents/queries'
import { formatCost } from '@/features/ai/usage/period'
import { formatDateTime } from '@/lib/format'
import { durationMs, formatDuration, placeLink, placeText, type PlaceLink } from './display'
import { RunStateBadge } from './RunBits'

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm break-words">{children}</dd>
    </div>
  )
}

export function Place({ link, text }: { link: PlaceLink | null; text: string }) {
  const className = 'underline underline-offset-2'
  if (!link) return <>{text}</>
  if (link.to === 'ticket') {
    return (
      <Link to="/tickets/$number" params={{ number: String(link.number) }} className={className}>
        {text}
      </Link>
    )
  }
  if (link.to === 'page') {
    return (
      <Link to="/go/page/$pageId" params={{ pageId: link.pageId }} className={className}>
        {text}
      </Link>
    )
  }
  return (
    <Link
      to="/c/$conversationId"
      params={{ conversationId: link.conversationId }}
      className={className}
    >
      {text}
    </Link>
  )
}

/** What a run is: agent, who asked, where (a link where the reader may follow it),
 *  state and why it stopped, take-ups, duration, tokens and cost, handover depth. */
export function RunHeader({ run, meId, now }: { run: Run; meId: string | undefined; now: number }) {
  const { t, i18n } = useTranslation()
  const usage = run.usage
  const cost = formatCost(usage.cost, i18n.language)
  return (
    <dl className="grid gap-x-6 gap-y-3 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-4">
      <Item label={t('runs.header.agent')}>
        <span className="inline-flex flex-wrap items-center gap-1.5">
          {run.agent_name}
          <AgentBadge />
        </span>
      </Item>
      <Item label={t('runs.header.asker')}>{run.asker_name}</Item>
      <Item label={t('runs.header.place')}>
        <Place link={placeLink(run, meId)} text={placeText(t, run)} />
      </Item>
      <Item label={t('runs.header.state')}>
        <RunStateBadge run={run} />
      </Item>
      {run.state === 'done' && (
        <Item label={t('runs.header.stopReason')}>{stopText(t, run.stop_reason)}</Item>
      )}
      {run.state === 'waiting' && run.wait_until && (
        <Item label={t('runs.header.waitUntil')}>
          {formatDateTime(run.wait_until, i18n.language)}
        </Item>
      )}
      <Item label={t('runs.header.started')}>
        {formatDateTime(run.started_at ?? run.created_at, i18n.language)}
      </Item>
      <Item label={t('runs.header.duration')}>{formatDuration(t, durationMs(run, now))}</Item>
      <Item label={t('runs.header.attempts')}>
        {t('runs.header.attemptsValue', { count: run.attempt, recoveries: run.recoveries })}
      </Item>
      <Item label={t('runs.header.steps')}>{run.steps}</Item>
      <Item label={t('runs.header.tokens')}>
        {t('runs.header.tokensValue', {
          tokensIn: usage.tokens_in.toLocaleString(i18n.language),
          tokensOut: usage.tokens_out.toLocaleString(i18n.language),
          cached: usage.tokens_cached.toLocaleString(i18n.language),
        })}
      </Item>
      <Item label={t('runs.header.cost')}>{cost ?? t('runs.header.noPrice')}</Item>
      <Item label={t('runs.header.chain')}>
        {run.chain_depth === 0
          ? t('runs.header.chainNone')
          : t('runs.header.chainDepth', { count: run.chain_depth })}
      </Item>
    </dl>
  )
}
