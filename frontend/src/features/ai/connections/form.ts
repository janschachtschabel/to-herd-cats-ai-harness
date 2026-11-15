import type { Schemas } from '@/lib/api'
import type { Connection, ConnectionKind, DataLocation, ParamFamily, Purpose } from '../display'

/** How the secret is given: kept as stored, a new value (stored encrypted), the name
 *  of an environment variable (`HERD_AI_…`), or removed. It is never shown again. */
export type SecretMode = 'keep' | 'value' | 'env' | 'none'

export interface ConnectionValues {
  name: string
  kind: ConnectionKind
  base_url: string
  secretMode: SecretMode
  secretValue: string
  secretEnv: string
  /** One model per line (or separated by commas); the first is the standard model. */
  models: string
  data_location: DataLocation
  purpose: Purpose
  /** Empty: the backend picks the family that fits the kind (creation only). */
  param_family: ParamFamily | ''
  max_concurrency: number
  requests_per_minute: number
  enabled: boolean
}

export function newConnectionValues(): ConnectionValues {
  return {
    name: '',
    kind: 'openai',
    base_url: '',
    secretMode: 'value',
    secretValue: '',
    secretEnv: '',
    models: '',
    data_location: 'external',
    purpose: 'chat',
    param_family: '',
    max_concurrency: 4,
    requests_per_minute: 60,
    enabled: true,
  }
}

export function connectionValues(connection: Connection): ConnectionValues {
  return {
    name: connection.name,
    kind: connection.kind,
    base_url: connection.base_url,
    secretMode: 'keep',
    secretValue: '',
    secretEnv: '',
    models: connection.models.join('\n'),
    data_location: connection.data_location,
    purpose: connection.purpose,
    param_family: connection.param_family,
    max_concurrency: connection.max_concurrency,
    requests_per_minute: connection.requests_per_minute,
    enabled: connection.enabled,
  }
}

export function parseModels(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((model) => model.trim())
    .filter((model) => model !== '')
}

function secretOf(values: ConnectionValues): Schemas['SecretIn'] | null | undefined {
  switch (values.secretMode) {
    case 'value':
      return values.secretValue === '' ? undefined : { value: values.secretValue }
    case 'env':
      return { env: values.secretEnv.trim() }
    case 'none':
      return null
    case 'keep':
      return undefined
  }
}

const numbers = (values: ConnectionValues) => ({
  max_concurrency: values.max_concurrency,
  requests_per_minute: values.requests_per_minute,
})

export function createBody(values: ConnectionValues): Schemas['ConnectionCreate'] {
  const models = parseModels(values.models)
  const secret = secretOf(values)
  return {
    name: values.name.trim(),
    kind: values.kind,
    base_url: values.base_url.trim() || null,
    ...(secret !== undefined && { secret }),
    models: models.length > 0 ? models : null,
    data_location: values.data_location,
    purpose: values.purpose,
    param_family: values.param_family || null,
    enabled: values.enabled,
    ...numbers(values),
  }
}

export function updateBody(values: ConnectionValues, version: number): Schemas['ConnectionUpdate'] {
  const secret = secretOf(values)
  return {
    name: values.name.trim(),
    base_url: values.base_url.trim(),
    ...(secret !== undefined && { secret }),
    models: parseModels(values.models),
    data_location: values.data_location,
    purpose: values.purpose,
    ...(values.param_family && { param_family: values.param_family }),
    enabled: values.enabled,
    ...numbers(values),
    version,
  }
}

/** The form field of a body path (`secret.value` → `secretValue`). */
export function fieldOf(path: string): string {
  if (path.startsWith('secret')) return path.endsWith('env') ? 'secretEnv' : 'secretValue'
  if (path.startsWith('models')) return 'models'
  return path.split('.')[0] ?? path
}
