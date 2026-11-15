import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import type { Message } from '@/lib/api'
import { useConversationView } from './ConversationContext'
import { MessageItem } from './MessageItem'
import { PendingItem } from './PendingItem'
import type { PendingMessage } from './pending'
import type { useMessages } from './queries'
import { buildTimeline, dayKey } from './timeline'

const NEAR = 80 // px: "at the bottom" / "at the top" within this distance

/** Today's and yesterday's day keys, taken when the list is first shown. */
function useDays(): { today: string; yesterday: string } {
  const [days] = useState(() => {
    const now = Date.now()
    return {
      today: dayKey(new Date(now).toISOString()),
      yesterday: dayKey(new Date(now - 86_400_000).toISOString()),
    }
  })
  return days
}

function DaySeparator({
  iso,
  today,
  yesterday,
}: {
  iso: string
  today: string
  yesterday: string
}) {
  const { t, i18n } = useTranslation()
  const key = dayKey(iso)
  const label =
    key === today
      ? t('messaging.days.today')
      : key === yesterday
        ? t('messaging.days.yesterday')
        : new Intl.DateTimeFormat(i18n.language, { dateStyle: 'full' }).format(new Date(iso))
  return (
    <div role="separator" aria-label={label} className="my-2 flex items-center gap-3">
      <span className="h-px flex-1 bg-border" />
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  )
}

function NewMarker() {
  const { t } = useTranslation()
  return (
    <div
      data-new-marker
      className="my-1 flex items-center gap-3 text-xs font-semibold text-destructive"
    >
      <span className="h-px flex-1 bg-destructive/60" />
      {t('messaging.list.new')}
    </div>
  )
}

/** Says a newly arrived message by someone else aloud (screen readers), once. */
function useArrivals(messages: readonly Message[], loaded: boolean, meId: string | undefined) {
  const { t } = useTranslation()
  const newest = useRef<string | null | undefined>(undefined)
  const [said, setSaid] = useState('')
  useEffect(() => {
    if (!loaded) return
    const top = messages[0]
    const before = newest.current
    newest.current = top?.id ?? null
    if (before === undefined || !top || top.id === before || top.author?.id === meId) return
    if (before !== null && top.id < before) return
    setSaid(t('messaging.list.arrived', { author: top.author?.name ?? '' }))
  }, [messages, loaded, meId, t])
  return said
}

/**
 * A conversation's history, oldest at the top: older messages load when one scrolls
 * up (or presses the button), day separators, "new" before the first unread message,
 * then one's own messages still on their way. Stays at the bottom while one is there.
 */
export function MessageList({
  list,
  pending,
  newBefore,
  emptyText,
}: {
  list: ReturnType<typeof useMessages>
  pending: PendingMessage[]
  newBefore: string | null
  emptyText: string
}) {
  const { t } = useTranslation()
  const { meId, highlight } = useConversationView()
  const rows = useMemo(
    () => buildTimeline(list.messages, pending, newBefore),
    [list.messages, pending, newBefore],
  )
  const scroller = useRef<HTMLDivElement>(null)
  const fromBottom = useRef(0)
  const placed = useRef(false)
  const said = useArrivals(list.messages, list.loaded, meId)
  const days = useDays()

  useLayoutEffect(() => {
    const el = scroller.current
    if (!el || rows.length === 0) return
    if (!placed.current) {
      placed.current = true
      const target =
        (highlight && el.querySelector(`[id="message-${highlight}"]`)) ||
        el.querySelector('[data-new-marker]')
      if (target) target.scrollIntoView({ block: highlight ? 'center' : 'start' })
      else el.scrollTop = el.scrollHeight
    } else if (fromBottom.current < NEAR) {
      el.scrollTop = el.scrollHeight
    } else {
      el.scrollTop = el.scrollHeight - el.clientHeight - fromBottom.current
    }
    fromBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight
  }, [rows, highlight])

  const onScroll = () => {
    const el = scroller.current
    if (!el) return
    fromBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight
    if (el.scrollTop < NEAR && list.hasOlder && !list.loadingOlder) list.loadOlder()
  }

  if (list.isPending) return <LoadingState />
  if (list.isError) return <ErrorState error={list.error} onRetry={list.refetch} />

  return (
    <div
      ref={scroller}
      onScroll={onScroll}
      className="min-h-0 flex-1 overflow-y-auto px-1"
      aria-label={t('messaging.list.label')}
      role="region"
      tabIndex={0}
    >
      {list.hasOlder && (
        <div className="flex justify-center py-2">
          <Button variant="outline" size="sm" onClick={list.loadOlder} disabled={list.loadingOlder}>
            {list.loadingOlder ? t('states.loadingMore') : t('messaging.list.older')}
          </Button>
        </div>
      )}
      {rows.length === 0 ? (
        <div className="py-6">
          <EmptyState text={emptyText} />
        </div>
      ) : (
        <ol className="flex flex-col gap-0.5 pb-2">
          {rows.map((row) => (
            <li key={row.key}>
              {row.kind === 'day' ? (
                <DaySeparator iso={row.date} {...days} />
              ) : row.kind === 'new' ? (
                <NewMarker />
              ) : row.kind === 'message' ? (
                <MessageItem message={row.message} />
              ) : (
                <PendingItem pending={row.pending} />
              )}
            </li>
          ))}
        </ol>
      )}
      <div role="status" aria-live="polite" className="sr-only">
        {said}
      </div>
    </div>
  )
}
