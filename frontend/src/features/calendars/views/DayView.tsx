import type { Day } from '../dates'
import { TimeGrid } from './TimeGrid'
import type { ViewProps } from './types'

/** One day with its hours. */
export function DayView({ anchor, ...view }: ViewProps & { anchor: Day }) {
  return <TimeGrid days={[anchor]} {...view} />
}
