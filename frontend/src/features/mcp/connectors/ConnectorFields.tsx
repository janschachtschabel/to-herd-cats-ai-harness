import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import { useOAuthClients } from '../connectorQueries'
import type { AuthKind } from '../display'
import type { ConnectorValues, KeyMode } from './connectorForm'

/** A connector's fields. The kind of access: a bearer token, a key in a header of its
 *  own name, or OAuth (with an OAuth app; connected afterwards). A key is only ever
 *  written; an OAuth connector's kind is fixed once made. `kinds`: what to offer
 *  (one's own connectors: no OAuth here, it comes with the server). */
export function ConnectorFields({
  form,
  creating = false,
  kinds,
  keyModes,
  keyStored = false,
}: {
  form: UseFormReturn<ConnectorValues>
  creating?: boolean
  kinds: readonly AuthKind[]
  keyModes: readonly KeyMode[]
  keyStored?: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const kind = form.watch('auth_kind')
  const mode = form.watch('keyMode')
  const clients = useOAuthClients(creating && kind === 'oauth')
  return (
    <>
      <Field label={t('mcp.connectors.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus={creating} {...form.register('name')} />}
      </Field>
      {kind === 'oauth' && !creating ? (
        <p className="text-sm text-muted-foreground">{t('mcp.connectors.oauthFixed')}</p>
      ) : (
        <Field label={t('mcp.connectors.fields.kind')} hint={t(`mcp.connectors.kindHints.${kind}`)}>
          {(props) => (
            <NativeSelect {...props} {...form.register('auth_kind')}>
              {kinds.map((value) => (
                <option key={value} value={value}>
                  {t(`mcp.connectors.kinds.${value}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      {kind === 'header' && (
        <Field
          label={t('mcp.connectors.fields.headerName')}
          hint={t('mcp.connectors.headerNameHint')}
          error={errors.header_name?.message}
        >
          {(props) => <Input {...props} autoComplete="off" {...form.register('header_name')} />}
        </Field>
      )}
      {kind === 'oauth' && creating && (
        <Field
          label={t('mcp.connectors.fields.oauthClient')}
          hint={
            !clients.isPending && clients.items.length === 0
              ? t('mcp.connectors.noClients')
              : t('mcp.connectors.oauthClientHint')
          }
          error={errors.oauth_client_id?.message}
        >
          {(props) => (
            <NativeSelect {...props} {...form.register('oauth_client_id')}>
              <option value="">{t('mcp.connectors.chooseClient')}</option>
              {clients.items.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      {kind !== 'oauth' && (
        <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
          <legend className="px-1 text-sm font-medium">{t('mcp.connectors.fields.key')}</legend>
          {!creating && (
            <p className="text-xs text-muted-foreground">
              {keyStored ? t('mcp.connectors.keyStored') : t('mcp.connectors.keyMissing')}
            </p>
          )}
          {keyModes.length > 1 && (
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {keyModes.map((value) => (
                <label key={value} className="inline-flex items-center gap-1.5 text-sm">
                  <input type="radio" value={value} {...form.register('keyMode')} />
                  {t(`mcp.connectors.keyModes.${value}`)}
                </label>
              ))}
            </div>
          )}
          {mode === 'value' && (
            <Field
              label={t('mcp.connectors.fields.keyValue')}
              hint={t('mcp.connectors.keyHint')}
              error={errors.keyValue?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  type="password"
                  autoComplete="new-password"
                  {...form.register('keyValue')}
                />
              )}
            </Field>
          )}
          {mode === 'env' && (
            <Field
              label={t('mcp.connectors.fields.keyEnv')}
              hint={t('mcp.connectors.keyEnvHint')}
              error={errors.keyEnv?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  autoComplete="off"
                  placeholder={t('mcp.connectors.keyEnvPlaceholder')}
                  {...form.register('keyEnv')}
                />
              )}
            </Field>
          )}
        </fieldset>
      )}
    </>
  )
}
