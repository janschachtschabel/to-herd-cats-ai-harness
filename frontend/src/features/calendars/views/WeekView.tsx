import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { addDays, startOfWeek, type Day } from '../dates'
import { TimeGrid } from './TimeGrid'
import type { ViewProps } from './types'

/** The week of `anchor` from the reader's week start; a day's head opens the day. */
export function WeekView({
  anchor,
  onOpenDay,
  ...view
}: ViewProps & { anchor: Day; onOpenDay: (day: Day) => void }) {
  const { i18n } = useTranslation()
  const days = useMemo(() => {
    const first = startOfWeek(anchor, i18n.language)
    return Array.from({ length: 7 }, (_, i) => addDays(first, i))
  }, [anchor, i18n.language])
  return <TimeGrid days={days} onOpenDay={onOpenDay} {...view} />
}
