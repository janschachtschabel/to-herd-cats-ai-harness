import type { PageMode } from '@/features/wiki/PageScreen'

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
