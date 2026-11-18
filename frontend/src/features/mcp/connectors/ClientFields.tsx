import { Search } from 'lucide-react'
import { useState } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, SaveError } from '@/features/shared/forms'
import { useDiscoverClient } from '../connectorQueries'
import { TOKEN_AUTHS, withDiscovery, type ClientSecretMode, type ClientValues } from './clientForm'

/** Reads a server's OAuth metadata and fills the empty fields with what it proposes. */
function Discover({ form }: { form: UseFormReturn<ClientValues> }) {
  const { t } = useTranslation()
  const discover = useDiscoverClient()
  const [url, setUrl] = useState('')
  const found = discover.data
  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-muted/30 p-3">
      <Field label={t('mcp.clients.discoverLabel')} hint={t('mcp.clients.discoverHint')}>
        {(props) => (
          <div className="flex gap-2">
            <Input
              {...props}
              type="url"
              inputMode="url"
              value={url}
              placeholder={t('mcp.servers.urlPlaceholder')}
              onChange={(event) => setUrl(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              disabled={url.trim() === '' || discover.isPending}
              onClick={() =>
                discover.mutate(url.trim(), {
                  onSuccess: (result) => {
                    if (result.status !== 'ok') return
                    for (const [key, value] of Object.entries(
                      withDiscovery(form.getValues(), result),
                    )) {
                      form.setValue(key as keyof ClientValues, value)
                    }
                  },
                })
              }
            >
              <Search aria-hidden />
              {t('mcp.clients.discover')}
            </Button>
          </div>
        )}
      </Field>
      {found && (
        <p role="status" className="text-xs">
          {found.status === 'ok'
            ? t('mcp.clients.discovered', {
                pkce: found.pkce ? t('mcp.clients.pkceYes') : t('mcp.clients.pkceNo'),
              })
            : t(`mcp.clients.discovery.${found.status}`)}
        </p>
      )}
      <SaveError error={discover.error} />
    </div>
  )
}

const MODES_NEW: readonly ClientSecretMode[] = ['none', 'value', 'env']
const MODES_EDIT: readonly ClientSecretMode[] = ['keep', 'none', 'value', 'env']

/** An OAuth app's fields: where it signs in, its id at the provider, its secret (none
 *  for a public app; only ever written), scopes, the resource it asks for and the
 *  issuer its answers must name (mix-up protection). */
export function ClientFields({
  form,
  creating = false,
  secretStored = false,
}: {
  form: UseFormReturn<ClientValues>
  creating?: boolean
  secretStored?: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const mode = form.watch('secretMode')
  const text = (name: keyof ClientValues, label: string, hint?: string) => (
    <Field label={label} hint={hint} error={errors[name]?.message}>
      {(props) => <Input {...props} autoComplete="off" {...form.register(name)} />}
    </Field>
  )
  return (
    <>
      {creating && <Discover form={form} />}
      {text('name', t('mcp.clients.fields.name'))}
      {text('authorization_endpoint', t('mcp.clients.fields.authorizationEndpoint'))}
      {text('token_endpoint', t('mcp.clients.fields.tokenEndpoint'))}
      {text(
        'revocation_endpoint',
        t('mcp.clients.fields.revocationEndpoint'),
        t('mcp.clients.optional'),
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {text('client_id', t('mcp.clients.fields.clientId'))}
        <Field label={t('mcp.clients.fields.tokenAuth')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('token_auth')}>
              {TOKEN_AUTHS.map((value) => (
                <option key={value} value={value}>
                  {t(`mcp.clients.tokenAuths.${value}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
        <legend className="px-1 text-sm font-medium">{t('mcp.clients.fields.secret')}</legend>
        {!creating && (
          <p className="text-xs text-muted-foreground">
            {secretStored ? t('mcp.clients.secretStored') : t('mcp.clients.secretNone')}
          </p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {(creating ? MODES_NEW : MODES_EDIT).map((value) => (
            <label key={value} className="inline-flex items-center gap-1.5 text-sm">
              <input type="radio" value={value} {...form.register('secretMode')} />
              {t(`mcp.clients.secretModes.${value}`)}
            </label>
          ))}
        </div>
        {mode === 'value' && (
          <Field label={t('mcp.clients.fields.secretValue')} error={errors.secretValue?.message}>
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
            label={t('mcp.connectors.fields.keyEnv')}
            hint={t('mcp.connectors.keyEnvHint')}
            error={errors.secretEnv?.message}
          >
            {(props) => (
              <Input
                {...props}
                autoComplete="off"
                placeholder={t('mcp.connectors.keyEnvPlaceholder')}
                {...form.register('secretEnv')}
              />
            )}
          </Field>
        )}
      </fieldset>
      {text('scopes', t('mcp.clients.fields.scopes'), t('mcp.clients.scopesHint'))}
      {text('resource', t('mcp.clients.fields.resource'), t('mcp.clients.resourceHint'))}
      {text('issuer', t('mcp.clients.fields.issuer'), t('mcp.clients.issuerHint'))}
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" {...form.register('issuer_in_response')} />
        {t('mcp.clients.fields.issuerInResponse')}
      </label>
    </>
  )
}
