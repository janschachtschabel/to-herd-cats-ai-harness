import {
  AtSign,
  CalendarClock,
  Check,
  CheckCheck,
  ClipboardCheck,
  FilePen,
  MessageCircleQuestion,
  MessageSquare,
  MessageSquareReply,
  OctagonAlert,
  ScrollText,
  ShieldCheck,
  UserCheck,
} from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { useMe } from '@/features/auth/queries'
import { AutomationSentence, ReviewDueSentence } from './Sentences'
import { conversationLabel } from '@/features/messaging/display'
import { plainMentions } from '@/features/messaging/mentions'
import { messageTarget, useOpenMessage } from '@/features/messaging/targets'
import { useSpaces } from '@/features/spaces/queries'
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
  const spaces = useSpaces()
  const spaceNames = useMemo(
    () => new Map(spaces.items.map((space) => [space.id, space.name])),
    [spaces.items],
  )
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
            <ActivityItem key={entry.id} entry={entry} spaceNames={spaceNames} />
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

const REASON_ICONS: Record<ActivityEntry['reason'], typeof AtSign> = {
  mention: AtSign,
  reply: MessageSquareReply,
  assignment: UserCheck,
  ticket_comment: MessageSquare,
  proposal: FilePen,
  approval: ShieldCheck,
  question: MessageCircleQuestion,
  run_stopped: OctagonAlert,
  skill_proposal: ScrollText,
  automation: CalendarClock,
  review_due: ClipboardCheck,
}

/** Where an entry happened, for its sentence: its conversation, or where a proposal
 *  without a thread belongs. */
function whereOf(
  t: TFunction,
  entry: ActivityEntry,
  meId: string | undefined,
  spaceNames: ReadonlyMap<string, string>,
): string {
  if (entry.conversation) return conversationLabel(t, entry.conversation, meId)
  if (entry.skill_proposal) {
    const spaceId = entry.skill_proposal.space_id
    if (!spaceId) return t('activity.skillProposalWhere.org')
    return spaceNames.get(spaceId) ?? t('activity.skillProposalWhere.space')
  }
  return t('activity.proposalWhere')
}

function ActivityItem({
  entry,
  spaceNames,
}: {
  entry: ActivityEntry
  spaceNames: ReadonlyMap<string, string>
}) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const open = useOpenMessage()
  const navigate = useNavigate()
  const read = useMarkActivityRead(entry.id)
  const done = useMarkActivityDone(entry.id)
  const unread = !entry.read_at && !entry.done_at
  const Icon = REASON_ICONS[entry.reason]
  const where = whereOf(t, entry, me?.user.id, spaceNames)
  const author = entry.author?.name ?? null
  // Entries with no place to open yet (an automation's view comes with its own screen).
  const opens = Boolean(
    (entry.conversation && entry.message_id) || entry.skill_proposal || entry.proposal,
  )

  const go = () => {
    if (!entry.read_at) read.mutate()
    if (entry.conversation && entry.message_id) {
      open(messageTarget(entry.conversation, entry.message_id, entry.parent_id))
    } else if (entry.skill_proposal) {
      const proposalId = entry.skill_proposal.id
      void navigate({ to: '/skill-proposals/$proposalId', params: { proposalId } })
    } else if (entry.proposal) {
      const { id: proposalId, space_id: spaceId } = entry.proposal
      void navigate({
        to: '/spaces/$spaceId/proposals/$proposalId',
        params: { spaceId, proposalId },
      })
    }
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
          {entry.reason === 'automation' ? (
            <AutomationSentence entry={entry} />
          ) : entry.reason === 'review_due' ? (
            <ReviewDueSentence entry={entry} />
          ) : (
            <>
              <span className="font-medium">{author ?? t('messaging.message.unknownAuthor')}</span>{' '}
              {entry.author?.type === 'agent' && (
                <>
                  <AgentBadge />{' '}
                </>
              )}
              {t(`activity.reasons.${entry.reason}`, { where })}
            </>
          )}
        </p>
        {entry.snippet && (
          <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
            {plainMentions(entry.snippet)}
          </p>
        )}
        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <time dateTime={entry.created_at}>{formatDateTime(entry.created_at, i18n.language)}</time>
          {entry.done_at && <Badge variant="secondary">{t('activity.done')}</Badge>}
        </p>
      </div>
      <div className="flex shrink-0 gap-1">
        {opens && (
          <Button size="sm" variant="outline" onClick={go}>
            {t('activity.open')}
          </Button>
        )}
        {!entry.done_at && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => done.mutate()}
            disabled={done.isPending}
            aria-label={author ? t('activity.markDone', { author }) : t('activity.markDoneEntry')}
          >
            <Check aria-hidden />
            {t('activity.doneAction')}
          </Button>
        )}
      </div>
    </li>
  )
}
