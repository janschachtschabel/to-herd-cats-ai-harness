import type { PageMode } from '@/features/wiki/PageScreen'
import type { OAuthStatus, RemoteStatus } from '@/features/mcp/display'

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** A message or thread id from the address bar, or nothing. */
function id(value: unknown): string | undefined {
  return typeof value === 'string' && ID.test(value) ? value.toLowerCase() : undefined
}

export interface MessageSearch {
  /** The thread to open beside the conversation. */
  thread?: string
  /** The message to scroll to and mark. */
  message?: string
}

export function messageSearch(search: Record<string, unknown>): MessageSearch {
  const thread = id(search.thread)
  const message = id(search.message)
  return { ...(thread ? { thread } : {}), ...(message ? { message } : {}) }
}

const PAGE_MODES: readonly PageMode[] = ['edit', 'live', 'versions']

export interface PageSearch extends MessageSearch {
  view?: PageMode
  /** Open the page's discussion. */
  discussion?: boolean
}

export function pageSearch(search: Record<string, unknown>): PageSearch {
  const view = PAGE_MODES.includes(search.view as PageMode) ? (search.view as PageMode) : undefined
  const discussion = search.discussion === true || search.discussion === 'true'
  return {
    ...(view ? { view } : {}),
    ...(discussion ? { discussion } : {}),
    ...messageSearch(search),
  }
}

/** Where to go after logging in: only paths inside this app. */
export function safeRedirect(value: unknown): string | undefined {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : undefined
}

export interface SkillsSearch {
  /** The proposals beside the skills (for those who decide them). */
  view?: 'proposals'
}

export function skillsSearch(search: Record<string, unknown>): SkillsSearch {
  return search.view === 'proposals' ? { view: 'proposals' } : {}
}

const REMOTE_STATUSES: readonly RemoteStatus[] = [
  'ok',
  'blocked',
  'timeout',
  'unreachable',
  'unauthorized',
  'forbidden',
  'not_found',
  'rate_limited',
  'redirect',
  'server_error',
  'too_large',
  'protocol_error',
  'secret_unavailable',
]

export interface ServerSearch {
  /** How reading the tools went right after the server was added. */
  read?: RemoteStatus
}

export function serverSearch(search: Record<string, unknown>): ServerSearch {
  const read = REMOTE_STATUSES.find((status) => status === search.read)
  return read ? { read } : {}
}

const OAUTH_STATUSES: readonly OAuthStatus[] = ['connected', 'denied', 'failed', 'invalid']

export interface OAuthDoneSearch {
  /** How the provider's sign-in ended (the API's fixed words; anything else: failed). */
  status: OAuthStatus
}

export function oauthDoneSearch(search: Record<string, unknown>): OAuthDoneSearch {
  return { status: OAUTH_STATUSES.find((status) => status === search.status) ?? 'failed' }
}
