import type { PageMode } from '@/features/wiki/PageScreen'
import type { OAuthStatus, RemoteStatus } from '@/features/mcp/display'

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** A message or thread id from the address bar, or nothing. */
function id(value: unknown): string | undefined {
  return typeof value === 'string' && ID.test(value) ? value.toLowerCase() : undefined
}

export interface MessageSearch {
  /** The thread to open beside the conversation. */
  thread?: string | undefined
  /** The message to scroll to and mark. */
  message?: string | undefined
}

/* Every validator below returns each of its keys, as undefined when refused: TanStack
 * Router lays the result over the raw search, so a key left out would keep its raw,
 * unchecked value (search.test.ts). */

export function messageSearch(search: Record<string, unknown>): MessageSearch {
  return { thread: id(search.thread), message: id(search.message) }
}

const PAGE_MODES: readonly PageMode[] = ['edit', 'live', 'versions']

export interface PageSearch extends MessageSearch {
  view?: PageMode | undefined
  /** Open the page's discussion. */
  discussion?: boolean | undefined
}

export function pageSearch(search: Record<string, unknown>): PageSearch {
  const view = PAGE_MODES.includes(search.view as PageMode) ? (search.view as PageMode) : undefined
  const discussion = search.discussion === true || search.discussion === 'true'
  return { view, discussion: discussion || undefined, ...messageSearch(search) }
}

/** Where to go after logging in: only paths inside this app. */
export function safeRedirect(value: unknown): string | undefined {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : undefined
}

/** The login page: where to go afterwards, and a refused sign-in's code. */
export interface LoginSearch {
  redirect?: string | undefined
  error?: string | undefined
  /** The provider was right; the sign-in waits for the second factor. */
  second_factor?: 'totp' | undefined
}

/** After a provider: the sign-in waits for the second factor (`totp`); nothing else. */
export function secondFactor(value: unknown): 'totp' | undefined {
  return value === 'totp' ? value : undefined
}

/** A sign-in's refusal code from the address (`oidc.<reason>`); nothing else. */
export function signInError(value: unknown): string | undefined {
  return typeof value === 'string' && /^oidc\.[a-z_]{1,40}$/.test(value) ? value : undefined
}

/** The profile after linking an account: the provider's key, or the refusal code. */
export interface ProfileSearch {
  linked?: string | undefined
  link_error?: string | undefined
}

export function profileSearch(search: Record<string, unknown>): ProfileSearch {
  const linked =
    typeof search.linked === 'string' && /^[a-z0-9-]{1,40}$/.test(search.linked)
      ? search.linked
      : undefined
  // Explicitly undefined when refused: the router lays this over the raw search.
  return { linked, link_error: signInError(search.link_error) }
}

export interface UsersSearch {
  /** Only the self-registered accounts awaiting approval (plan M9 task 5b). */
  filter?: 'pending' | undefined
}

export function usersSearch(search: Record<string, unknown>): UsersSearch {
  return { filter: search.filter === 'pending' ? 'pending' : undefined }
}

export interface SkillsSearch {
  /** The proposals beside the skills (for those who decide them). */
  view?: 'proposals' | undefined
}

export function skillsSearch(search: Record<string, unknown>): SkillsSearch {
  return { view: search.view === 'proposals' ? 'proposals' : undefined }
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
  read?: RemoteStatus | undefined
}

export function serverSearch(search: Record<string, unknown>): ServerSearch {
  return { read: REMOTE_STATUSES.find((status) => status === search.read) }
}

const OAUTH_STATUSES: readonly OAuthStatus[] = [
  'connected',
  'denied',
  'failed',
  'invalid',
  'issuer_mismatch',
]

export interface OAuthDoneSearch {
  /** How the provider's sign-in ended (the API's fixed words; anything else: failed). */
  status: OAuthStatus
}

export function oauthDoneSearch(search: Record<string, unknown>): OAuthDoneSearch {
  return { status: OAUTH_STATUSES.find((status) => status === search.status) ?? 'failed' }
}
