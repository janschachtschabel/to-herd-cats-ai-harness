import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Field } from '@/features/shared/forms'
import { CONNECTION_KINDS, DATA_LOCATIONS, PARAM_FAMILIES, PURPOSES } from '../display'
import type { ConnectionValues, SecretMode } from './form'

/** The fields of a connection. The kind is fixed once created; the secret is only
 *  ever written (a value, an environment variable, or removed), never read back. */
export function ConnectionFields({
  form,
  creating = false,
  secretSet = false,
}: {
  form: UseFormReturn<ConnectionValues>
  creating?: boolean
  secretSet?: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const mode = form.watch('secretMode')
  const modes: SecretMode[] = creating ? ['value', 'env', 'none'] : ['keep', 'value', 'env', 'none']
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('ai.connections.fields.name')} error={errors.name?.message}>
          {(props) => <Input {...props} autoFocus={creating} {...form.register('name')} />}
        </Field>
        <Field
          label={t('ai.connections.fields.kind')}
          hint={creating ? t('ai.connections.kindHint') : t('ai.connections.kindFixed')}
        >
          {(props) => (
            <NativeSelect {...props} disabled={!creating} {...form.register('kind')}>
              {CONNECTION_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`ai.kinds.${kind}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      <Field
        label={t('ai.connections.fields.baseUrl')}
        hint={t('ai.connections.baseUrlHint')}
        error={errors.base_url?.message}
      >
        {(props) => <Input {...props} type="url" inputMode="url" {...form.register('base_url')} />}
      </Field>
      <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
        <legend className="px-1 text-sm font-medium">{t('ai.connections.fields.secret')}</legend>
        {!creating && (
          <p className="text-xs text-muted-foreground">
            {secretSet ? t('ai.connections.secretStored') : t('ai.connections.secretMissing')}
          </p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {modes.map((value) => (
            <label key={value} className="inline-flex items-center gap-1.5 text-sm">
              <input type="radio" value={value} {...form.register('secretMode')} />
              {t(`ai.connections.secretModes.${value}`)}
            </label>
          ))}
        </div>
        {mode === 'value' && (
          <Field label={t('ai.connections.fields.secretValue')} error={errors.secretValue?.message}>
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="new-password"
                {...form.register('secretValue')}
              />
            )}
          </Field>
        )}
        {mode === 'env' && (
          <Field
            label={t('ai.connections.fields.secretEnv')}
            hint={t('ai.connections.secretEnvHint')}
            error={errors.secretEnv?.message}
          >
            {(props) => (
              <Input
                {...props}
                autoComplete="off"
                placeholder={t('ai.connections.secretEnvPlaceholder')}
                {...form.register('secretEnv')}
              />
            )}
          </Field>
        )}
      </fieldset>
      <Field
        label={t('ai.connections.fields.models')}
        hint={t('ai.connections.modelsHint')}
        error={errors.models?.message}
      >
        {(props) => <Textarea {...props} rows={3} {...form.register('models')} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label={t('ai.connections.fields.dataLocation')}
          hint={t('ai.connections.dataLocationHint')}
        >
          {(props) => (
            <NativeSelect {...props} {...form.register('data_location')}>
              {DATA_LOCATIONS.map((location) => (
                <option key={location} value={location}>
                  {t(`ai.locations.${location}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('ai.connections.fields.purpose')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('purpose')}>
              {PURPOSES.map((purpose) => (
                <option key={purpose} value={purpose}>
                  {t(`ai.purposes.${purpose}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('ai.connections.fields.paramFamily')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('param_family')}>
              {creating && <option value="">{t('ai.connections.paramFamilyAuto')}</option>}
              {PARAM_FAMILIES.map((family) => (
                <option key={family} value={family}>
                  {family}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label={t('ai.connections.fields.maxConcurrency')}
          error={errors.max_concurrency?.message}
        >
          {(props) => (
            <Input
              {...props}
              type="number"
              min={1}
              {...form.register('max_concurrency', { valueAsNumber: true })}
            />
          )}
        </Field>
        <Field
          label={t('ai.connections.fields.requestsPerMinute')}
          error={errors.requests_per_minute?.message}
        >
          {(props) => (
            <Input
              {...props}
              type="number"
              min={1}
              {...form.register('requests_per_minute', { valueAsNumber: true })}
            />
          )}
        </Field>
      </div>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" {...form.register('enabled')} />
        {t('ai.connections.fields.enabled')}
      </label>
    </>
  )
}
