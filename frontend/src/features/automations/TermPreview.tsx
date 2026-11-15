import { useTranslation } from 'react-i18next'
import { errorMessage } from '@/lib/errors'
import { termText } from './display'
import { useTermPreview, type ScheduleIn } from './queries'

/** The next terms of the schedule as typed, from the API (the same rules as saving),
 *  in the reader's time; a refusal in words (`automation.too_frequent`, ...). */
export function TermPreview({ schedule }: { schedule: ScheduleIn | null }) {
  const { t, i18n } = useTranslation()
  const preview = useTermPreview(schedule)
  const zone = schedule && 'time_zone' in schedule ? schedule.time_zone : null
  let body
  if (!schedule) {
    body = <p className="text-muted-foreground">{t('automations.form.previewWaiting')}</p>
  } else if (preview.isError) {
    body = (
      <p className="text-destructive" role="alert">
        {errorMessage(t, preview.error)}
      </p>
    )
  } else if (!preview.data) {
    body = <p className="text-muted-foreground">{t('states.loading')}</p>
  } else if (preview.data.length === 0) {
    body = <p className="text-muted-foreground">{t('automations.form.previewNone')}</p>
  } else {
    body = (
      <ul aria-labelledby="term-preview" className="flex flex-col gap-0.5 tabular-nums">
        {preview.data.map((term) => (
          <li key={term}>
            <time dateTime={term}>{termText(t, term, i18n.language, zone)}</time>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <section
      aria-labelledby="term-preview"
      aria-live="polite"
      className="rounded-lg border bg-muted/30 p-3 text-sm"
    >
      <h3 id="term-preview" className="font-medium">
        {t('automations.form.preview')}
      </h3>
      <p className="mb-1 text-xs text-muted-foreground">{t('automations.form.previewHint')}</p>
      {body}
    </section>
  )
}
