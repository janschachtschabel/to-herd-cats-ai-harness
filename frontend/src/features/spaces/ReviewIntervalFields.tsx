import { useId } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { Schemas } from '@/lib/api'

/** The interval after which the space's published pages are due for review again
 *  (`space.manage`): off, or 7 to 730 days (the bounds come from the API schema). */
export const DEFAULT_REVIEW_DAYS = 90

export function ReviewIntervalFields({ form }: { form: UseFormReturn<Schemas['SpaceUpdateIn']> }) {
  const { t } = useTranslation()
  const toggleId = useId()
  const daysId = useId()
  const errorId = `${daysId}-error`
  const value = form.watch('review_interval_days')
  const on = value !== null && value !== undefined
  const error = form.formState.errors.review_interval_days
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{t('spaces.review.title')}</legend>
      <p className="text-xs text-muted-foreground">{t('spaces.review.hint')}</p>
      <div className="flex items-center gap-2">
        <input
          id={toggleId}
          type="checkbox"
          className="size-4 accent-primary"
          checked={on}
          onChange={(event) =>
            form.setValue(
              'review_interval_days',
              event.target.checked ? DEFAULT_REVIEW_DAYS : null,
              {
                shouldDirty: true,
                shouldValidate: false,
              },
            )
          }
        />
        <Label htmlFor={toggleId}>{t('spaces.review.on')}</Label>
      </div>
      {on && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={daysId}>{t('spaces.review.days')}</Label>
          <Input
            id={daysId}
            type="number"
            inputMode="numeric"
            min={7}
            max={730}
            step={1}
            className="w-32"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            {...form.register('review_interval_days', { valueAsNumber: true })}
          />
          {error && (
            <p id={errorId} className="text-xs text-destructive">
              {t('spaces.review.range')}
            </p>
          )}
        </div>
      )}
    </fieldset>
  )
}
