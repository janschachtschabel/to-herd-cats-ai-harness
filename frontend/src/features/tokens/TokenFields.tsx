import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { TokenValues } from './form'

/** The spaces one may limit a token to: those its owner reads (an external agent: its
 *  spaces), as far as loaded. */
export interface SpaceChoices {
  items: readonly { id: string; name: string }[]
  isPending: boolean
  hasMore: boolean
  loadMore: () => void
}

const MODES = ['read', 'write'] as const

/** Read only, or read and write (what each lets a client do, in words). */
export function ModeFields({
  form,
  forAgent,
}: {
  form: UseFormReturn<TokenValues>
  forAgent: boolean
}) {
  const { t } = useTranslation()
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{t('tokens.fields.mode')}</legend>
      {MODES.map((mode) => (
        <label key={mode} className="flex items-start gap-2 text-sm">
          <input
            type="radio"
            value={mode}
            className="mt-1 accent-primary"
            {...form.register('mode')}
          />
          <span>
            <span className="font-medium">{t(`tokens.modes.${mode}`)}</span>
            <span className="block text-xs text-muted-foreground">
              {t(forAgent ? `tokens.modes.agentExplain.${mode}` : `tokens.modes.explain.${mode}`)}
            </span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}

/** All of the owner's spaces, or chosen ones (at least one). */
export function ScopeFields({
  form,
  spaces,
  forAgent,
}: {
  form: UseFormReturn<TokenValues>
  spaces: SpaceChoices
  forAgent: boolean
}) {
  const { t } = useTranslation()
  const scope = form.watch('scope')
  const chosen = form.watch('space_ids')
  const error = form.formState.errors.space_ids
  const toggle = (id: string, on: boolean) =>
    form.setValue('space_ids', on ? [...chosen, id] : chosen.filter((c) => c !== id), {
      shouldValidate: form.formState.isSubmitted,
    })
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{t('tokens.fields.scope')}</legend>
      <label className="flex items-center gap-2 text-sm">
        <input type="radio" value="all" className="accent-primary" {...form.register('scope')} />
        {forAgent ? t('tokens.scope.allAgent') : t('tokens.scope.all')}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="radio" value="chosen" className="accent-primary" {...form.register('scope')} />
        {t('tokens.scope.chosen')}
      </label>
      {scope === 'chosen' && (
        <div className="ml-6 flex flex-col gap-1.5">
          {spaces.isPending ? (
            <p className="text-xs text-muted-foreground">{t('states.loading')}</p>
          ) : spaces.items.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t('tokens.scope.none')}</p>
          ) : (
            <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto rounded-md border p-2">
              {spaces.items.map((space) => (
                <li key={space.id}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      checked={chosen.includes(space.id)}
                      onChange={(event) => toggle(space.id, event.target.checked)}
                    />
                    {space.name}
                  </label>
                </li>
              ))}
            </ul>
          )}
          {spaces.hasMore && (
            <div>
              <Button type="button" size="xs" variant="outline" onClick={spaces.loadMore}>
                {t('actions.loadMore')}
              </Button>
            </div>
          )}
          {error && (
            <p role="alert" className="text-xs text-destructive">
              {t('tokens.scope.required')}
            </p>
          )}
        </div>
      )}
    </fieldset>
  )
}
