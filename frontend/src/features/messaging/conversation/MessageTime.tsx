import { useTranslation } from 'react-i18next'
import { formatDateTime } from '@/lib/format'

/** The time of a message ("14:05"); the full date and time on hover and for readers. */
export function MessageTime({ iso }: { iso: string }) {
  const { i18n } = useTranslation()
  const time = new Intl.DateTimeFormat(i18n.language, { timeStyle: 'short' }).format(new Date(iso))
  const full = formatDateTime(iso, i18n.language)
  return (
    <time dateTime={iso} title={full} className="text-xs text-muted-foreground">
      <span aria-hidden>{time}</span>
      <span className="sr-only">{full}</span>
    </time>
  )
}
