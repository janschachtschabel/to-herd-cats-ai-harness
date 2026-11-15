import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { DATA_LOCATIONS } from '@/features/ai/display'
import { Field } from '@/features/shared/forms'
import { useConnectors, useOAuthClients } from '../connectorQueries'
import { CONNECTOR_USES } from '../display'
import type { ServerValues } from './serverForm'

/** A server's fields: name, address (https), where its data goes, and whose access it
 *  uses: none, a shared connector, or each person's own (optionally with an OAuth app
 *  people connect with). */
export function ServerFields({
  form,
  creating = false,
}: {
  form: UseFormReturn<ServerValues>
  creating?: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const scope = form.watch('connector_scope')
  const connectors = useConnectors('shared', scope === 'shared')
  const clients = useOAuthClients(scope === 'personal')
  return (
    <>
      <Field label={t('mcp.servers.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus={creating} {...form.register('name')} />}
      </Field>
      <Field
        label={t('mcp.servers.fields.url')}
        hint={t('mcp.servers.urlHint')}
        error={errors.url?.message}
      >
        {(props) => (
          <Input
            {...props}
            type="url"
            inputMode="url"
            placeholder={t('mcp.servers.urlPlaceholder')}
            {...form.register('url')}
          />
        )}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label={t('mcp.servers.fields.dataLocation')}
          hint={t('mcp.servers.dataLocationHint')}
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
        <Field label={t('mcp.servers.fields.access')} hint={t(`mcp.access.hints.${scope}`)}>
          {(props) => (
            <NativeSelect {...props} {...form.register('connector_scope')}>
              {CONNECTOR_USES.map((use) => (
                <option key={use} value={use}>
                  {t(`mcp.access.${use}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      {scope === 'shared' && (
        <Field
          label={t('mcp.servers.fields.connector')}
          hint={
            !connectors.isPending && connectors.items.length === 0
              ? t('mcp.servers.noConnectors')
              : undefined
          }
          error={errors.connector_id?.message}
        >
          {(props) => (
            <NativeSelect {...props} {...form.register('connector_id')}>
              <option value="">{t('mcp.servers.chooseConnector')}</option>
              {connectors.items.map((connector) => (
                <option key={connector.id} value={connector.id}>
                  {connector.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      {scope === 'personal' && (
        <Field label={t('mcp.servers.fields.oauthClient')} hint={t('mcp.servers.oauthClientHint')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('oauth_client_id')}>
              <option value="">{t('mcp.servers.personalToken')}</option>
              {clients.items.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" {...form.register('enabled')} />
        {t('mcp.servers.fields.enabled')}
      </label>
    </>
  )
}
