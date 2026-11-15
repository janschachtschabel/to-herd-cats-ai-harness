import type { Schemas } from '@/lib/api'
import type { DataLocation } from '@/features/ai/display'
import type { ConnectorUse, Server } from '../display'

/** The fields of a server's form. `connector_id` counts only for a shared access,
 *  `oauth_client_id` only for a personal one (empty: people bring a token). */
export interface ServerValues {
  name: string
  url: string
  data_location: DataLocation
  connector_scope: ConnectorUse
  connector_id: string
  oauth_client_id: string
  enabled: boolean
}

export function newServerValues(): ServerValues {
  return {
    name: '',
    url: '',
    data_location: 'external',
    connector_scope: 'none',
    connector_id: '',
    oauth_client_id: '',
    enabled: true,
  }
}

export function serverValues(server: Server): ServerValues {
  return {
    name: server.name,
    url: server.url,
    data_location: server.data_location,
    connector_scope: server.connector_scope,
    connector_id: server.connector_id ?? '',
    oauth_client_id: server.oauth_client_id ?? '',
    enabled: server.enabled,
  }
}

function access(values: ServerValues) {
  return {
    connector_scope: values.connector_scope,
    connector_id: values.connector_scope === 'shared' ? values.connector_id || null : null,
    oauth_client_id: values.connector_scope === 'personal' ? values.oauth_client_id || null : null,
  }
}

export function createBody(values: ServerValues): Schemas['ServerCreate'] {
  return {
    name: values.name.trim(),
    url: values.url.trim(),
    data_location: values.data_location,
    enabled: values.enabled,
    ...access(values),
  }
}

export function updateBody(values: ServerValues, version: number): Schemas['ServerUpdate'] {
  return {
    name: values.name.trim(),
    url: values.url.trim(),
    data_location: values.data_location,
    enabled: values.enabled,
    ...access(values),
    version,
  }
}

/** Whether saving withdraws every approval: a new address is another server. */
export function urlChanged(server: Server, values: ServerValues): boolean {
  return values.url.trim() !== server.url
}
