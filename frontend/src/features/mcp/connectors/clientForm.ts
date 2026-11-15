import type { Schemas } from '@/lib/api'
import type { OAuthClient } from '../display'

/** How the app's client secret is given: none (a public app, PKCE only), kept, a new
 *  value (stored encrypted) or an environment variable `HERD_AI_…`. Never shown. */
export type ClientSecretMode = 'none' | 'keep' | 'value' | 'env'
export type TokenAuth = Schemas['TokenAuth']
export const TOKEN_AUTHS: readonly TokenAuth[] = ['client_secret_post', 'client_secret_basic']

export interface ClientValues {
  name: string
  authorization_endpoint: string
  token_endpoint: string
  revocation_endpoint: string
  client_id: string
  secretMode: ClientSecretMode
  secretValue: string
  secretEnv: string
  token_auth: TokenAuth
  scopes: string
  resource: string
  /** On new endpoints: shared connectors keep their tokens (personal ones never). */
  keep_shared_connectors: boolean
}

export function newClientValues(): ClientValues {
  return {
    name: '',
    authorization_endpoint: '',
    token_endpoint: '',
    revocation_endpoint: '',
    client_id: '',
    secretMode: 'none',
    secretValue: '',
    secretEnv: '',
    token_auth: 'client_secret_post',
    scopes: '',
    resource: '',
    keep_shared_connectors: false,
  }
}

export function clientValues(client: OAuthClient): ClientValues {
  return {
    name: client.name,
    authorization_endpoint: client.authorization_endpoint,
    token_endpoint: client.token_endpoint,
    revocation_endpoint: client.revocation_endpoint ?? '',
    client_id: client.client_id,
    secretMode: 'keep',
    secretValue: '',
    secretEnv: '',
    token_auth: client.token_auth,
    scopes: client.scopes,
    resource: client.resource ?? '',
    keep_shared_connectors: false,
  }
}

/** The proposal of a discovery, over the values typed so far (empty fields only). */
export function withDiscovery(
  values: ClientValues,
  found: Schemas['DiscoveryOut'],
): Partial<ClientValues> {
  const fill = (current: string, proposed: string | null) =>
    current.trim() === '' && proposed ? proposed : current
  return {
    authorization_endpoint: fill(values.authorization_endpoint, found.authorization_endpoint),
    token_endpoint: fill(values.token_endpoint, found.token_endpoint),
    revocation_endpoint: fill(values.revocation_endpoint, found.revocation_endpoint),
    scopes: fill(values.scopes, found.scopes),
    resource: fill(values.resource, found.resource),
  }
}

function secretOf(values: ClientValues): Schemas['SecretIn'] | null | undefined {
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

const optional = (text: string) => text.trim() || null

function fields(values: ClientValues) {
  return {
    name: values.name.trim(),
    authorization_endpoint: values.authorization_endpoint.trim(),
    token_endpoint: values.token_endpoint.trim(),
    revocation_endpoint: optional(values.revocation_endpoint),
    client_id: values.client_id.trim(),
    token_auth: values.token_auth,
    scopes: values.scopes.trim(),
    resource: optional(values.resource),
  }
}

export function createBody(values: ClientValues): Schemas['ClientCreate'] {
  return { ...fields(values), client_secret: secretOf(values) ?? null }
}

export function updateBody(values: ClientValues, version: number): Schemas['ClientUpdate'] {
  const secret = secretOf(values)
  return {
    ...fields(values),
    ...(secret !== undefined && { client_secret: secret }),
    keep_shared_connectors: values.keep_shared_connectors,
    version,
  }
}

export function missingSecret(values: ClientValues): string[] {
  if (values.secretMode === 'value' && values.secretValue === '') return ['secretValue']
  if (values.secretMode === 'env' && values.secretEnv.trim() === '') return ['secretEnv']
  return []
}

export function fieldOf(path: string): string {
  if (path.startsWith('client_secret')) return path.endsWith('env') ? 'secretEnv' : 'secretValue'
  return path.split('.')[0] ?? path
}

/** Whether saving disconnects every connector through the app: a new authorization,
 *  token or revocation endpoint (tokens go there). */
export function endpointsMoved(client: OAuthClient, values: ClientValues): boolean {
  return (
    values.authorization_endpoint.trim() !== client.authorization_endpoint ||
    values.token_endpoint.trim() !== client.token_endpoint ||
    (values.revocation_endpoint.trim() || null) !== (client.revocation_endpoint ?? null)
  )
}
