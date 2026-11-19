import { useTranslation } from 'react-i18next'
import type { ActivityEntry } from '@/lib/api'
import { formatDateTime, formatDay } from '@/lib/format'

const ANSWERS = ['needs_action', 'accepted', 'tentative', 'declined'] as const

/** An invitation (or what changed about it since) or replies to one's own event (plan
 *  M10 task 4): the event by title. The server lists the entry only while the person
 *  attends the event, so its title is hers to see. */
export function CalendarSentence({ entry }: { entry: ActivityEntry }) {
  const { t } = useTranslation()
  const event = entry.calendar_event
  if (!event) return <>{t(`activity.reasons.${entry.reason}`)}</>
  const title = event.title
  if (entry.reason === 'invite_reply') return <>{t('activity.invitation.replied', { title })}</>
  return (
    <>
      {event.cancelled
        ? t('activity.invitation.cancelled', { title })
        : t('activity.invitation.invited', { title })}
    </>
  )
}

/** When the event begins (an all-day event: its day) and the person's own answer. */
export function CalendarDetails({ entry }: { entry: ActivityEntry }) {
  const { t, i18n } = useTranslation()
  const event = entry.calendar_event
  if (!event) return null
  const when = event.all_day
    ? formatDay(event.starts_at.slice(0, 10), i18n.language)
    : formatDateTime(event.starts_at, i18n.language)
  const answer = (ANSWERS as readonly string[]).includes(event.response ?? '')
    ? t(`activity.invitation.answers.${event.response}`)
    : null
  return (
    <p className="mt-0.5 text-sm text-muted-foreground">
      <time dateTime={event.starts_at}>{when}</time>
      {answer && !event.cancelled && (
        <>
          {' · '}
          {t('activity.invitation.answer', { answer })}
        </>
      )}
    </p>
  )
}
