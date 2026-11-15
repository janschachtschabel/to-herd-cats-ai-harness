import type { Schemas } from '@/lib/api'
import type { AuthKind, Connector } from '../display'

/** How a key is given: kept as stored, a new value (stored encrypted), or the name of
 *  an environment variable `HERD_AI_…` (shared connectors only). Never shown again. */
export type KeyMode = 'keep' | 'value' | 'env'

export interface ConnectorValues {
  name: string
  auth_kind: AuthKind
  header_name: string
  keyMode: KeyMode
  keyValue: string
  keyEnv: string
  oauth_client_id: string
}

export function newConnectorValues(name = ''): ConnectorValues {
  return {
    name,
    auth_kind: 'bearer',
    header_name: '',
    keyMode: 'value',
    keyValue: '',
    keyEnv: '',
    oauth_client_id: '',
  }
}

export function connectorValues(connector: Connector): ConnectorValues {
  return {
    name: connector.name,
    auth_kind: connector.auth_kind,
    header_name: connector.header_name ?? '',
    keyMode: 'keep',
    keyValue: '',
    keyEnv: '',
    oauth_client_id: connector.oauth_client_id ?? '',
  }
}

function keyOf(values: ConnectorValues): Schemas['SecretIn'] | undefined {
  if (values.auth_kind === 'oauth') return undefined
  if (values.keyMode === 'value') return { value: values.keyValue }
  if (values.keyMode === 'env') return { env: values.keyEnv.trim() }
  return undefined
}

export function createBody(
  values: ConnectorValues,
  mcpServerId: string | null = null,
): Schemas['ConnectorCreate'] {
  const oauth = values.auth_kind === 'oauth'
  const secret = keyOf(values)
  return {
    name: values.name.trim(),
    auth_kind: values.auth_kind,
    header_name: values.auth_kind === 'header' ? values.header_name.trim() : null,
    oauth_client_id: oauth ? values.oauth_client_id || null : null,
    mcp_server_id: mcpServerId,
    ...(secret && { secret }),
  }
}

export function updateBody(values: ConnectorValues, version: number): Schemas['ConnectorUpdate'] {
  const secret = keyOf(values)
  return {
    name: values.name.trim(),
    ...(values.auth_kind !== 'oauth' && {
      auth_kind: values.auth_kind,
      header_name: values.auth_kind === 'header' ? values.header_name.trim() : null,
    }),
    ...(secret && { secret }),
    version,
  }
}

/** What the form must hold beyond the body's schema: a key for a new bearer/header
 *  connector (or a changed one), a header's name, an OAuth app. Field → message key. */
export function missingFields(values: ConnectorValues, creating: boolean): string[] {
  const missing: string[] = []
  if (values.auth_kind === 'header' && values.header_name.trim() === '') {
    missing.push('header_name')
  }
  if (values.auth_kind === 'oauth') {
    if (creating && values.oauth_client_id === '') missing.push('oauth_client_id')
    return missing
  }
  if (values.keyMode === 'value' && values.keyValue === '') missing.push('keyValue')
  if (values.keyMode === 'env' && values.keyEnv.trim() === '') missing.push('keyEnv')
  return missing
}

/** The form field of a body path (`secret.value` → `keyValue`). */
export function fieldOf(path: string): string {
  if (path.startsWith('secret')) return path.endsWith('env') ? 'keyEnv' : 'keyValue'
  return path.split('.')[0] ?? path
}
