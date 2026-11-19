import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { calendarLabel, eventTitle, whenText, type CalendarInfo } from './display'
import type { Occurrence } from './queries'

/** A read-only look at an occurrence from the window (what the list holds: no text, no
 *  attendees). Changing it comes with the event dialog (plan M10 Task 11). */
export function EventPeek({
  occurrence,
  calendar,
  zone,
  onClose,
}: {
  occurrence: Occurrence | null
  calendar: CalendarInfo | undefined
  zone: string
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  return (
    <Dialog open={occurrence !== null} onOpenChange={(open) => !open && onClose()}>
      {occurrence && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle className={occurrence.redacted ? 'italic' : undefined}>
              {eventTitle(t, occurrence)}
            </DialogTitle>
            <DialogDescription>{whenText(t, occurrence, zone, locale)}</DialogDescription>
          </DialogHeader>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {occurrence.location && (
              <>
                <dt className="text-muted-foreground">{t('calendar.event.location')}</dt>
                <dd>{occurrence.location}</dd>
              </>
            )}
            <dt className="text-muted-foreground">{t('calendar.event.calendar')}</dt>
            <dd>{calendarLabel(t, calendar)}</dd>
          </dl>
          {occurrence.recurring && (
            <p className="text-sm text-muted-foreground">{t('calendar.event.series')}</p>
          )}
          {occurrence.status === 'cancelled' && (
            <p className="text-sm font-medium">{t('calendar.event.cancelledNote')}</p>
          )}
          {occurrence.redacted && (
            <p className="text-sm text-muted-foreground">{t('calendar.event.redacted')}</p>
          )}
        </DialogContent>
      )}
    </Dialog>
  )
}
