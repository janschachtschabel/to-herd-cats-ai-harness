import type { DataLocation } from '@/features/ai/display'
import type { Schemas } from '@/lib/api'
import type { AuthKind, CatalogEntry, ConnectorUse } from '../display'

export interface InstallValues {
  name: string
  base_url: string
  connector_scope: ConnectorUse
  auth_kind: AuthKind | ''
  keyMode: 'value' | 'env'
  keyValue: string
  keyEnv: string
  client_id: string
  clientSecretMode: 'none' | 'value' | 'env'
  clientSecretValue: string
  clientSecretEnv: string
  data_location: DataLocation
  enabled: boolean
}

export function installValues(entry: CatalogEntry): InstallValues {
  const scope = entry.connector_scopes[0] ?? 'none'
  return {
    name: entry.name,
    base_url: entry.base_url?.default ?? '',
    connector_scope: scope,
    auth_kind: entry.auth?.[0]?.kind ?? '',
    keyMode: 'value',
    keyValue: '',
    keyEnv: '',
    client_id: '',
    clientSecretMode: 'none',
    clientSecretValue: '',
    clientSecretEnv: '',
    data_location: entry.data_location ?? 'external',
    enabled: true,
  }
}

/** What the installation will need beyond the server: a shared key, an OAuth app. */
export type Needs = 'nothing' | 'key' | 'oauth' | 'personal'

export function needsOf(values: Pick<InstallValues, 'connector_scope' | 'auth_kind'>): Needs {
  if (values.connector_scope === 'none' || values.auth_kind === '') return 'nothing'
  if (values.auth_kind === 'oauth') return 'oauth'
  return values.connector_scope === 'shared' ? 'key' : 'personal'
}

function secret(mode: 'none' | 'value' | 'env', value: string, env: string) {
  if (mode === 'value') return { value }
  if (mode === 'env') return { env: env.trim() }
  return null
}

export function installBody(entry: CatalogEntry, values: InstallValues): Schemas['InstallIn'] {
  const needs = needsOf(values)
  return {
    connector_scope: values.connector_scope,
    auth_kind:
      values.connector_scope === 'none' || values.auth_kind === '' ? null : values.auth_kind,
    name: values.name.trim() || null,
    base_url: entry.base_url ? values.base_url.trim() || null : null,
    secret: needs === 'key' ? secret(values.keyMode, values.keyValue, values.keyEnv) : null,
    client_id: needs === 'oauth' ? values.client_id.trim() || null : null,
    client_secret:
      needs === 'oauth'
        ? secret(values.clientSecretMode, values.clientSecretValue, values.clientSecretEnv)
        : null,
    data_location: values.data_location,
    enabled: values.enabled,
  }
}

export function missingInstall(values: InstallValues): string[] {
  const needs = needsOf(values)
  const missing: string[] = []
  if (needs === 'key') {
    if (values.keyMode === 'value' && values.keyValue === '') missing.push('keyValue')
    if (values.keyMode === 'env' && values.keyEnv.trim() === '') missing.push('keyEnv')
  }
  if (needs === 'oauth') {
    if (values.client_id.trim() === '') missing.push('client_id')
    if (values.clientSecretMode === 'value' && values.clientSecretValue === '') {
      missing.push('clientSecretValue')
    }
    if (values.clientSecretMode === 'env' && values.clientSecretEnv.trim() === '') {
      missing.push('clientSecretEnv')
    }
  }
  return missing
}

export function fieldOf(path: string): string {
  if (path.startsWith('client_secret')) {
    return path.endsWith('env') ? 'clientSecretEnv' : 'clientSecretValue'
  }
  if (path.startsWith('secret')) return path.endsWith('env') ? 'keyEnv' : 'keyValue'
  return path.split('.')[0] ?? path
}
