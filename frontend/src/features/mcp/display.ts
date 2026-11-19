import type { Schemas } from '@/lib/api'

export type Server = Schemas['ServerOut']
export type CreatedServer = Schemas['CreatedServerOut']
export type Tool = Schemas['ToolOut']
export type Connector = Schemas['ConnectorOut']
export type OAuthClient = Schemas['ClientOut']
export type CatalogEntry = Schemas['CatalogEntry']
export type CatalogProblem = Schemas['ProblemOut']
export type PersonalServer = Schemas['PersonalServerOut']
export type RemoteStatus = Schemas['RemoteStatus']
export type RefreshResult = Schemas['RefreshOut']
export type ConnectorUse = Schemas['ConnectorUse']
export type AuthKind = Schemas['AuthKind']
export type Classification = Schemas['Classification']
export type Localized = Schemas['Localized']

/** How a provider's sign-in ended (`/ai/oauth/done?status=…`, the API's fixed words). */
export type OAuthStatus = 'connected' | 'denied' | 'failed' | 'invalid' | 'issuer_mismatch'

export const CONNECTOR_USES: readonly ConnectorUse[] = ['none', 'shared', 'personal']
export const AUTH_KINDS: readonly AuthKind[] = ['bearer', 'header', 'oauth']
export const CLASSIFICATIONS: readonly Classification[] = ['read', 'write']

/** How a tool is shown: a tool the server no longer lists is "missing" whatever its
 *  state; a pending one is "new". */
export type ToolView = 'new' | 'approved' | 'blocked' | 'changed' | 'missing'

export function toolView(tool: Pick<Tool, 'state' | 'missing'>): ToolView {
  if (tool.missing) return 'missing'
  return tool.state === 'pending' ? 'new' : tool.state
}

/** A tool waiting for the admin: new, or changed since its approval. */
export function toolNeedsAttention(tool: Pick<Tool, 'state' | 'missing'>): boolean {
  const view = toolView(tool)
  return view === 'new' || view === 'changed'
}

/** What changed since a tool's approval: its description, its input schema; null when
 *  the approved version was not kept (an approval from before it was). */
export type ChangedPart = 'description' | 'schema'

export function changedParts(
  tool: Pick<
    Tool,
    'description' | 'input_schema' | 'approved_description' | 'approved_input_schema'
  >,
): ChangedPart[] | null {
  if (tool.approved_description == null || tool.approved_input_schema == null) return null
  const parts: ChangedPart[] = []
  if (tool.approved_description !== tool.description) parts.push('description')
  if (JSON.stringify(tool.approved_input_schema) !== JSON.stringify(tool.input_schema)) {
    parts.push('schema')
  }
  return parts
}

/** A remote server's answer (test, refresh) as a tone; the words say what happened. */
export function remoteTone(status: RemoteStatus): 'ok' | 'refused' | 'failed' {
  if (status === 'ok') return 'ok'
  if (status === 'unauthorized' || status === 'forbidden' || status === 'rate_limited') {
    return 'refused'
  }
  return 'failed'
}

export const TONE_CLASSES = {
  ok: 'text-emerald-700 dark:text-emerald-400',
  refused: 'text-amber-700 dark:text-amber-400',
  failed: 'text-destructive',
} as const

/** What a connector holds: an OAuth one is connected or not; a key is stored
 *  encrypted or named as an environment variable. The secret itself is never shown. */
export type ConnectorState = 'connected' | 'disconnected' | 'enc' | 'env'

export function connectorState(
  connector: Pick<Connector, 'auth_kind' | 'has_secret' | 'secret_kind'>,
): ConnectorState {
  if (connector.auth_kind === 'oauth') return connector.has_secret ? 'connected' : 'disconnected'
  return connector.secret_kind === 'env' ? 'env' : 'enc'
}

/** A catalogue text in the reader's language (German when there is none). */
export function localized(text: Localized | null | undefined, language: string): string {
  if (!text) return ''
  return language.startsWith('en') ? text.en : text.de
}

/** The provider's sign-in page, only if it is an https address: the browser is never
 *  sent anywhere else, whatever an answer says. */
export function safeAuthorizationUrl(url: string): string | null {
  try {
    return new URL(url).protocol === 'https:' ? url : null
  } catch {
    return null
  }
}
