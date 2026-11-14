import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Field } from '@/features/shared/forms'
import type { LimitErrors, LimitInput } from './budget'

/** The two daily limits of a budget; either may stay empty, not both. */
export function LimitFields({
  value,
  onChange,
  errors,
}: {
  value: LimitInput
  onChange: (value: LimitInput) => void
  errors: LimitErrors
}) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field
        label={t('ai.budgets.tokens')}
        hint={t('ai.budgets.tokensHint')}
        error={errors.tokens ? t('ai.budgets.errors.tokens') : undefined}
      >
        {(props) => (
          <Input
            {...props}
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            value={value.tokens}
            onChange={(event) => onChange({ ...value, tokens: event.target.value })}
          />
        )}
      </Field>
      <Field
        label={t('ai.budgets.cost')}
        hint={t('ai.budgets.costHint')}
        error={errors.cost ? t('ai.budgets.errors.cost') : undefined}
      >
        {(props) => (
          <Input
            {...props}
            inputMode="decimal"
            autoComplete="off"
            value={value.cost}
            onChange={(event) => onChange({ ...value, cost: event.target.value })}
          />
        )}
      </Field>
      {errors.missing && (
        <p role="alert" className="text-sm text-destructive sm:col-span-2">
          {t('ai.budgets.errors.limitMissing')}
        </p>
      )}
    </div>
  )
}
