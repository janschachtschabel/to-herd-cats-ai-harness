import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/lib/api'

const POLICIES: readonly Schemas['AgentWritePolicy'][] = ['propose', 'direct']

/** How agents change this space's pages (`space.manage`): propose for a moderator to
 *  accept, or write directly when their level allows it. Governance, so shown to
 *  whoever manages the space, with or without AI of their own. */
export function AgentWritePolicyFields({
  form,
}: {
  form: UseFormReturn<Schemas['SpaceUpdateIn']>
}) {
  const { t } = useTranslation()
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{t('spaces.agentWrite.title')}</legend>
      <p className="text-xs text-muted-foreground">{t('spaces.agentWrite.hint')}</p>
      <div className="flex flex-col gap-1.5">
        {POLICIES.map((value) => (
          <label key={value} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              className="mt-1"
              value={value}
              {...form.register('agent_write_policy')}
            />
            <span>
              <span className="font-medium">{t(`spaces.agentWrite.values.${value}`)}</span>
              <span className="block text-xs text-muted-foreground">
                {t(`spaces.agentWrite.explain.${value}`)}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
