import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { Choice, Segment } from './merge'

const SIDES = ['base', 'proposed', 'current'] as const
const CHOICES: readonly Choice[] = ['current', 'proposed', 'both']

/** One region where the proposal and the page changed the same lines: the three
 *  versions side by side (stacked on a phone) and the moderator's choice. */
export function ConflictRegion({
  number,
  segment,
  choice,
  onChoose,
}: {
  number: number
  segment: Segment
  choice: Choice
  onChoose: (choice: Choice) => void
}) {
  const { t } = useTranslation()
  const name = useId()
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">
        {t('proposals.merge.region', { number })}
      </legend>
      <div className="grid gap-2 md:grid-cols-3">
        {SIDES.map((side) => (
          <div key={side} className="min-w-0">
            <p className="mb-1 text-xs text-muted-foreground">
              {t(`proposals.merge.sides.${side}`)}
            </p>
            <pre className="min-h-8 overflow-x-auto rounded-md border bg-muted/40 p-2 text-xs whitespace-pre-wrap">
              {segment[side].length > 0 ? segment[side].join('\n') : t('proposals.merge.nothing')}
            </pre>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {CHOICES.map((value) => (
          <label key={value} className="inline-flex items-center gap-1.5 text-sm">
            <input
              type="radio"
              name={name}
              className="accent-primary"
              checked={choice === value}
              onChange={() => onChoose(value)}
            />
            {t(`proposals.merge.choices.${value}`)}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
