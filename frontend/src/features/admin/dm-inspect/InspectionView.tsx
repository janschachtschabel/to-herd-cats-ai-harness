import { Clock } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { RUN_STOPPED } from '@/features/agents/display'
import { RunStoppedNotice } from '@/features/agents/RunStoppedNotice'
import { MessageMarkdown } from '@/features/messaging/MessageMarkdown'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { ApiError, type InspectableDm, type Inspection } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useInspectedMessages } from './queries'
import { minutesLeft } from './time'

function useNow(everyMs: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(timer)
  }, [everyMs])
  return now
}

/** A granted inspection: who talks, why one looks, until when, and the messages,
 *  read only (newest first, replies included); an agent's with the AI mark, a run's
 *  stop as its notice. */
export function InspectionView({
  inspection,
  dm,
  onEnd,
}: {
  inspection: Inspection
  dm: InspectableDm
  onEnd: () => void
}) {
  const { t, i18n } = useTranslation()
  const messages = useInspectedMessages(inspection.id)
  const left = minutesLeft(inspection.expires_at, useNow(30_000))
  const expired =
    left === 0 ||
    (messages.error instanceof ApiError && messages.error.code === 'dm_inspection.not_found')
  return (
    <div>
      <PageHeader
        title={t('dmInspect.viewTitle', { people: dm.participants.map((p) => p.name).join(', ') })}
        description={t('dmInspect.viewReason', { reason: inspection.reason })}
        actions={
          <Button variant="outline" onClick={onEnd}>
            {t('dmInspect.end')}
          </Button>
        }
      />
      <Alert className="mb-4">
        <Clock aria-hidden />
        <AlertDescription>
          {expired
            ? t('dmInspect.expired')
            : t('dmInspect.until', {
                when: formatDateTime(inspection.expires_at, i18n.language),
                count: left,
              })}
        </AlertDescription>
      </Alert>
      {expired ? null : messages.isPending ? (
        <LoadingState />
      ) : messages.isError ? (
        <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
      ) : messages.items.length === 0 ? (
        <EmptyState text={t('dmInspect.empty')} />
      ) : (
        <ol className="flex flex-col gap-2" aria-label={t('dmInspect.messages')}>
          {messages.items.map((message) =>
            message.kind === 'system' && message.system?.key === RUN_STOPPED ? (
              <li key={message.id}>
                <RunStoppedNotice message={message} />
              </li>
            ) : (
              <li key={message.id} className="rounded-md border px-3 py-2">
                <p className="flex flex-wrap items-baseline gap-2 text-sm">
                  <span className="font-semibold">
                    {message.author?.name ?? t('messaging.message.unknownAuthor')}
                  </span>
                  {message.kind === 'agent' && <AgentBadge />}
                  <time dateTime={message.created_at} className="text-xs text-muted-foreground">
                    {formatDateTime(message.created_at, i18n.language)}
                  </time>
                  {message.parent_id && (
                    <span className="text-xs text-muted-foreground">{t('dmInspect.inThread')}</span>
                  )}
                </p>
                {message.deleted_at ? (
                  <p className="text-sm text-muted-foreground italic">
                    {t('messaging.message.deleted')}
                  </p>
                ) : (
                  <MessageMarkdown markdown={message.body_md} />
                )}
              </li>
            ),
          )}
        </ol>
      )}
      {!expired && (
        <LoadMore
          hasMore={messages.hasMore}
          loading={messages.loadingMore}
          onLoad={messages.loadMore}
        />
      )}
    </div>
  )
}
