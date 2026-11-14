import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/lib/api'
import { AI_POLICIES, DATA_LOCATIONS } from '../display'

/** The space's AI policy in its settings: any connection, only connections at chosen
 *  locations, or no AI at all (the space is invisible to AI). */
export function SpaceAiPolicyFields({ form }: { form: UseFormReturn<Schemas['SpaceUpdateIn']> }) {
  const { t } = useTranslation()
  const policy = form.watch('ai_policy')
  const error = form.formState.errors.allowed_locations?.message
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{t('ai.policy.title')}</legend>
      <p className="text-xs text-muted-foreground">{t('ai.policy.hint')}</p>
      <div className="flex flex-col gap-1.5">
        {AI_POLICIES.map((value) => (
          <label key={value} className="flex items-start gap-2 text-sm">
            <input type="radio" className="mt-1" value={value} {...form.register('ai_policy')} />
            <span>
              <span className="font-medium">{t(`ai.policy.values.${value}`)}</span>
              <span className="block text-xs text-muted-foreground">
                {t(`ai.policy.explain.${value}`)}
              </span>
            </span>
          </label>
        ))}
      </div>
      {policy === 'restricted' && (
        <fieldset className="mt-1 flex flex-col gap-1 pl-6">
          <legend className="text-sm font-medium">{t('ai.policy.locations')}</legend>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {DATA_LOCATIONS.map((location) => (
              <label key={location} className="inline-flex items-center gap-1.5 text-sm">
                <input type="checkbox" value={location} {...form.register('allowed_locations')} />
                {t(`ai.locations.${location}`)}
              </label>
            ))}
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </fieldset>
      )}
    </fieldset>
  )
}
