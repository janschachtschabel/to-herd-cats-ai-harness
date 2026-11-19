import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { TONE_DOT, type CalendarInfo } from './display'

export interface CalendarGroup {
  spaceId: string
  spaceName: string
  calendars: (CalendarInfo & { id: string })[]
}

/** The calendars by space, each with a switch to show or hide it; a calendar one may
 *  only read says so (from `my_role`, never a role name in the UI). */
export function CalendarList({
  groups,
  hidden,
  onToggle,
}: {
  groups: CalendarGroup[]
  hidden: ReadonlySet<string>
  onToggle: (calendarId: string) => void
}) {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="calendar-list-heading" className="flex flex-col gap-3">
      <h2 id="calendar-list-heading" className="text-sm font-semibold">
        {t('calendar.list.title')}
      </h2>
      {groups.length === 0 && (
        <p className="text-sm text-muted-foreground">{t('calendar.list.empty')}</p>
      )}
      {groups.map((group) => (
        <fieldset key={group.spaceId} className="flex min-w-0 flex-col gap-1">
          <legend className="mb-1 truncate text-xs font-medium text-muted-foreground">
            {group.spaceName}
          </legend>
          {group.calendars.map((calendar) => (
            <label
              key={calendar.id}
              className="flex min-w-0 cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 text-sm hover:bg-muted"
            >
              <input
                type="checkbox"
                className="size-4 shrink-0 accent-primary"
                checked={!hidden.has(calendar.id)}
                onChange={() => onToggle(calendar.id)}
              />
              <span
                aria-hidden
                className={cn('size-2.5 shrink-0 rounded-full', TONE_DOT[calendar.color])}
              />
              <span className="min-w-0 flex-1 truncate">{calendar.label}</span>{' '}
              {!calendar.abilities.write && (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t('calendar.list.readOnly')}
                </span>
              )}
            </label>
          ))}
        </fieldset>
      ))}
    </section>
  )
}
