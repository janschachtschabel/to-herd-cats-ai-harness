import { AtSign, Check, CheckCheck, MessageSquareReply } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { conversationLabel } from '@/features/messaging/display'
import { plainMentions } from '@/features/messaging/mentions'
import { messageTarget, useOpenMessage } from '@/features/messaging/targets'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import type { ActivityEntry } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  useActivity,
  useMarkActivityDone,
  useMarkActivityRead,
  useReadAllActivity,
} from './queries'

/** "Activity" (spec 6.2): what concerns me, newest first. Each entry leads into its
 *  conversation (and counts as read); "done" puts it away. */
export function ActivityPage() {
  const { t } = useTranslation()
  const [includeDone, setIncludeDone] = useState(false)
  const activity = useActivity(includeDone)
  const readAll = useReadAllActivity()
  return (
    <div>
      <PageHeader
        title={t('activity.title')}
        description={t('activity.description')}
        actions={
          <Button variant="outline" onClick={() => readAll.mutate()} disabled={readAll.isPending}>
            <CheckCheck aria-hidden />
            {t('activity.readAll')}
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b">
        <div role="tablist" aria-label={t('activity.tabs')} className="flex">
          <span
            role="tab"
            aria-selected
            className="border-b-2 border-primary px-3 py-2 text-sm font-medium"
          >
            {t('activity.forMe')}
          </span>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            className="accent-primary"
            checked={includeDone}
            onChange={(event) => setIncludeDone(event.target.checked)}
          />
          {t('activity.showDone')}
        </label>
      </div>
      {readAll.error ? <p role="alert">{errorMessage(t, readAll.error)}</p> : null}
      {activity.isPending ? (
        <LoadingState />
      ) : activity.isError ? (
        <ErrorState error={activity.error} onRetry={() => void activity.refetch()} />
      ) : activity.items.length === 0 ? (
        <EmptyState text={t('activity.empty')} />
      ) : (
        <ul className="flex flex-col gap-2">
          {activity.items.map((entry) => (
            <ActivityItem key={entry.id} entry={entry} />
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={activity.hasMore}
        loading={activity.loadingMore}
        onLoad={activity.loadMore}
      />
    </div>
  )
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const open = useOpenMessage()
  const read = useMarkActivityRead(entry.id)
  const done = useMarkActivityDone(entry.id)
  const unread = !entry.read_at && !entry.done_at
  const Icon = entry.reason === 'mention' ? AtSign : MessageSquareReply
  const where = conversationLabel(t, entry.conversation, me?.user.id)
  const author = entry.author?.name ?? t('messaging.message.unknownAuthor')

  const go = () => {
    if (!entry.read_at) read.mutate()
    open(messageTarget(entry.conversation, entry.message_id, entry.parent_id))
  }

  return (
    <li
      className={cn(
        'flex items-start gap-3 rounded-lg border p-3',
        unread ? 'border-primary/40 bg-primary/5' : 'bg-background',
        entry.done_at && 'opacity-70',
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          {unread && <span className="sr-only">{t('activity.unread')} </span>}
          <span className="font-medium">{author}</span>{' '}
          {t(`activity.reasons.${entry.reason}`, { where })}
        </p>
        <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
          {plainMentions(entry.snippet)}
        </p>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <time dateTime={entry.created_at}>{formatDateTime(entry.created_at, i18n.language)}</time>
          {entry.done_at && <Badge variant="secondary">{t('activity.done')}</Badge>}
        </p>
      </div>
      <div className="flex shrink-0 gap-1">
        <Button size="sm" variant="outline" onClick={go}>
          {t('activity.open')}
        </Button>
        {!entry.done_at && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => done.mutate()}
            disabled={done.isPending}
            aria-label={t('activity.markDone', { author })}
          >
            <Check aria-hidden />
            {t('activity.doneAction')}
          </Button>
        )}
      </div>
    </li>
  )
}
