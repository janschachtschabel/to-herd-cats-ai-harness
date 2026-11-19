import type { FieldErrors, Resolver } from 'react-hook-form'
import type { Schemas } from '@/lib/api'
import { bodyResolver } from '@/lib/formResolver'
import i18n from '@/lib/i18n'
import { bodySchema } from '@/lib/schemas'
import type { OidcProvider } from './queries'

export type ProviderKind = Schemas['ProviderKind']
/** How the client secret is given: kept, a new value (stored encrypted), an environment
 *  variable `HERD_OIDC_…`, or none (a public client; never for Google). Never shown. */
export type SecretMode = 'keep' | 'value' | 'env' | 'none'

export interface ProviderValues {
  kind: ProviderKind
  key: string
  name: string
  issuer: string
  client_id: string
  secretMode: SecretMode
  secretValue: string
  secretEnv: string
  scopes: string
  trust_email: boolean
  allow_signup: boolean
  /** One domain per line. */
  domains: string
  enabled: boolean
}

export function newProviderValues(kind: ProviderKind): ProviderValues {
  return {
    kind,
    key: '',
    name: '',
    issuer: '',
    client_id: '',
    secretMode: 'value',
    secretValue: '',
    secretEnv: '',
    scopes: 'openid email profile',
    trust_email: false,
    allow_signup: false,
    domains: '',
    enabled: false,
  }
}

export function providerValues(provider: OidcProvider): ProviderValues {
  return {
    kind: provider.kind,
    key: provider.key,
    name: provider.name,
    issuer: provider.issuer,
    client_id: provider.client_id,
    secretMode: 'keep',
    secretValue: '',
    secretEnv: '',
    scopes: provider.scopes,
    trust_email: provider.trust_email,
    allow_signup: provider.allow_signup,
    domains: provider.allowed_domains.join('\n'),
    enabled: provider.enabled,
  }
}

/** The secret choices offered: a stored secret is replaced, never removed; only a
 *  generic provider may be a public client. */
export function secretModes(kind: ProviderKind, creating: boolean): SecretMode[] {
  if (!creating) return ['keep', 'value', 'env']
  return kind === 'google' ? ['value', 'env'] : ['value', 'env', 'none']
}

export function domainsOf(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((d) => d.trim())
    .filter(Boolean)
}

function secretOf(values: ProviderValues): Schemas['OidcSecretIn'] | null | undefined {
  switch (values.secretMode) {
    case 'value':
      return { value: values.secretValue }
    case 'env':
      return { env: values.secretEnv.trim() }
    case 'none':
      return null
    case 'keep':
      return undefined
  }
}

export function createBody(values: ProviderValues): Schemas['ProviderCreate'] {
  const common = {
    kind: values.kind,
    client_id: values.client_id.trim(),
    client_secret: secretOf(values) ?? null,
    allow_signup: values.allow_signup,
    allowed_domains: domainsOf(values.domains),
    enabled: values.enabled,
  }
  if (values.kind === 'google') return common
  return {
    ...common,
    key: values.key.trim(),
    name: values.name.trim(),
    issuer: values.issuer.trim(),
    scopes: values.scopes.trim(),
    trust_email: values.trust_email,
  }
}

export function updateBody(values: ProviderValues, version: number): Schemas['ProviderUpdate'] {
  const secret = secretOf(values)
  const generic = values.kind === 'generic' && {
    name: values.name.trim(),
    issuer: values.issuer.trim(),
    scopes: values.scopes.trim(),
    trust_email: values.trust_email,
  }
  return {
    version,
    client_id: values.client_id.trim(),
    allow_signup: values.allow_signup,
    allowed_domains: domainsOf(values.domains),
    enabled: values.enabled,
    ...(secret && { client_secret: secret }),
    ...generic,
  }
}

export function fieldOf(path: string): string {
  if (path.startsWith('client_secret')) return path.endsWith('env') ? 'secretEnv' : 'secretValue'
  if (path.startsWith('allowed_domains')) return 'domains'
  return path.split('.')[0] ?? path
}

/** What the body's schema cannot say: required fields of the kind, a secret typed as
 *  chosen, domains whenever self-registration is on, and (at a generic provider)
 *  trusted addresses for it. */
export function missing(values: ProviderValues, creating: boolean): Record<string, string> {
  const out: Record<string, string> = {}
  const required = i18n.t('validation.required')
  if (values.kind === 'generic' && creating) {
    for (const name of ['key', 'name', 'issuer'] as const) {
      if (values[name].trim() === '') out[name] = required
    }
  }
  if (values.client_id.trim() === '') out.client_id = required
  if (values.secretMode === 'value' && values.secretValue === '') out.secretValue = required
  if (values.secretMode === 'env' && values.secretEnv.trim() === '') out.secretEnv = required
  if (values.allow_signup && domainsOf(values.domains).length === 0) {
    out.domains = i18n.t('oidcAdmin.form.domainsRequired')
  }
  if (values.kind === 'generic' && values.allow_signup && !values.trust_email) {
    out.allow_signup = i18n.t('oidcAdmin.form.signupNeedsTrust')
  }
  return out
}

export function providerResolver(provider: OidcProvider | undefined): Resolver<ProviderValues> {
  const base = provider
    ? bodyResolver(
        bodySchema('ProviderUpdate'),
        (v: ProviderValues) => updateBody(v, provider.version),
        fieldOf,
      )
    : bodyResolver(bodySchema('ProviderCreate'), createBody, fieldOf)
  return async (values, context, options) => {
    const result = await base(values, context, options)
    const own = missing(values, provider === undefined)
    if (Object.keys(own).length === 0) return result
    const errors = Object.fromEntries(
      Object.entries(own).map(([field, message]) => [field, { type: 'required', message }]),
    )
    return { values: {}, errors: { ...errors, ...result.errors } as FieldErrors<ProviderValues> }
  }
}
