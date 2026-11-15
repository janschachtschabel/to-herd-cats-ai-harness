import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { DATA_LOCATIONS } from '@/features/ai/display'
import { Field } from '@/features/shared/forms'
import { localized, type CatalogEntry } from '../display'
import { needsOf, type InstallValues } from './installForm'

const radio = 'inline-flex items-start gap-1.5 text-sm'

function KeyInputs({
  form,
  mode,
  modes,
  prefix,
}: {
  form: UseFormReturn<InstallValues>
  mode: string
  modes: readonly string[]
  prefix: 'key' | 'clientSecret'
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const modeField = prefix === 'key' ? 'keyMode' : 'clientSecretMode'
  const valueField = prefix === 'key' ? 'keyValue' : 'clientSecretValue'
  const envField = prefix === 'key' ? 'keyEnv' : 'clientSecretEnv'
  return (
    <>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {modes.map((value) => (
          <label key={value} className={radio}>
            <input type="radio" value={value} {...form.register(modeField)} />
            {t(`mcp.catalog.install.secretModes.${value}`)}
          </label>
        ))}
      </div>
      {mode === 'value' && (
        <Field
          label={t(`mcp.catalog.install.fields.${valueField}`)}
          error={errors[valueField]?.message}
        >
          {(props) => (
            <Input
              {...props}
              type="password"
              autoComplete="new-password"
              {...form.register(valueField)}
            />
          )}
        </Field>
      )}
      {mode === 'env' && (
        <Field
          label={t('mcp.connectors.fields.keyEnv')}
          hint={t('mcp.connectors.keyEnvHint')}
          error={errors[envField]?.message}
        >
          {(props) => (
            <Input
              {...props}
              autoComplete="off"
              placeholder={t('mcp.connectors.keyEnvPlaceholder')}
              {...form.register(envField)}
            />
          )}
        </Field>
      )}
    </>
  )
}

/** The few things the admin brings to a template: a name, the instance's address (if
 *  it may differ), whose access, how to sign in, and the key or the OAuth app. */
export function InstallFields({
  entry,
  form,
}: {
  entry: CatalogEntry
  form: UseFormReturn<InstallValues>
}) {
  const { t, i18n } = useTranslation()
  const errors = form.formState.errors
  const values = form.watch()
  const needs = needsOf(values)
  const auth = entry.auth ?? []
  const option = auth.find((a) => a.kind === values.auth_kind)
  return (
    <>
      <Field label={t('mcp.servers.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} {...form.register('name')} />}
      </Field>
      {entry.base_url && (
        <Field
          label={t('mcp.catalog.install.fields.baseUrl')}
          hint={localized(entry.base_url.note, i18n.language) || undefined}
          error={errors.base_url?.message}
        >
          {(props) => (
            <Input {...props} type="url" inputMode="url" {...form.register('base_url')} />
          )}
        </Field>
      )}
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1 text-sm font-medium">{t('mcp.servers.fields.access')}</legend>
        {entry.connector_scopes.map((scope) => (
          <label key={scope} className={radio}>
            <input
              type="radio"
              className="mt-1"
              value={scope}
              {...form.register('connector_scope')}
            />
            <span>
              <span className="font-medium">{t(`mcp.access.${scope}`)}</span>
              <span className="block text-xs text-muted-foreground">
                {t(`mcp.access.hints.${scope}`)}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {values.connector_scope !== 'none' && auth.length > 0 && (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-sm font-medium">
            {t('mcp.catalog.install.fields.auth')}
          </legend>
          {auth.map((a) => (
            <label key={a.kind} className={radio}>
              <input type="radio" className="mt-1" value={a.kind} {...form.register('auth_kind')} />
              <span className="font-medium">{t(`mcp.connectors.kinds.${a.kind}`)}</span>
            </label>
          ))}
          {option?.note && (
            <p className="text-xs text-muted-foreground">{localized(option.note, i18n.language)}</p>
          )}
        </fieldset>
      )}
      {needs === 'key' && (
        <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
          <legend className="px-1 text-sm font-medium">{t('mcp.connectors.fields.key')}</legend>
          <KeyInputs form={form} mode={values.keyMode} modes={['value', 'env']} prefix="key" />
        </fieldset>
      )}
      {needs === 'oauth' && (
        <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
          <legend className="px-1 text-sm font-medium">{t('mcp.catalog.install.oauthApp')}</legend>
          <Field label={t('mcp.clients.fields.clientId')} error={errors.client_id?.message}>
            {(props) => <Input {...props} autoComplete="off" {...form.register('client_id')} />}
          </Field>
          <KeyInputs
            form={form}
            mode={values.clientSecretMode}
            modes={['none', 'value', 'env']}
            prefix="clientSecret"
          />
        </fieldset>
      )}
      {needs === 'personal' && (
        <p className="text-sm text-muted-foreground">{t('mcp.catalog.install.personalToken')}</p>
      )}
      <Field label={t('mcp.servers.fields.dataLocation')} hint={t('mcp.servers.dataLocationHint')}>
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
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" {...form.register('enabled')} />
        {t('mcp.servers.fields.enabled')}
      </label>
    </>
  )
}
