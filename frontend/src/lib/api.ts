import createClient, { type Middleware } from 'openapi-fetch'
import type { components, paths } from './api-types'

export type Schemas = components['schemas']
export type Me = Schemas['MeOut']
export type User = Schemas['UserOut']
export type Group = Schemas['GroupOut']
export type GroupMember = Schemas['GroupMemberOut']
export type Space = Schemas['SpaceOut']
export type SpaceKind = Schemas['SpaceKind']
export type SpaceRole = Schemas['SpaceRole']
export type SpaceMember = Schemas['SpaceMemberOut']
export type SystemRole = Schemas['SystemRole']
export type AuditEntry = Schemas['AuditOut']
export type Permission = Schemas['Action']
export type DirectoryEntry = Schemas['DirectoryEntryOut']
export type WikiPage = Schemas['PageOut']
export type TreeNode = Schemas['TreeNodeOut']
export type TrashedPage = Schemas['TrashedPageOut']
export type Tag = Schemas['TagOut']
export type Attachment = Schemas['AttachmentOut']
export type VersionSummary = Schemas['VersionSummaryOut']
export type Version = Schemas['VersionOut']
export type Diff = Schemas['DiffOut']
export type SearchHit = Schemas['PageHitOut']
export type MessageHit = Schemas['MessageHitOut']
export type ImportResult = Schemas['ImportResultOut']
export type Conversation = Schemas['ConversationOut']
export type DmConversation = Schemas['DmOut']
export type Message = Schemas['MessageOut']
export type MessageWrite = Schemas['MessageWriteOut']
export type Reaction = Schemas['ReactionOut']
export type Unread = Schemas['UnreadOut']
export type SystemEntry = Schemas['SystemEntryOut']
export type ActivityEntry = Schemas['ActivityOut']
export type ActivityCount = Schemas['ActivityCountOut']
export type InspectableDm = Schemas['InspectableDmOut']
export type Ticket = Schemas['TicketOut']
export type TicketSummary = Schemas['TicketSummaryOut']
export type TicketHit = Schemas['TicketHitOut']
export type TicketStatus = Schemas['StatusOut']
export type Epic = Schemas['EpicOut']
export type Board = Schemas['BoardOut']
export type BoardColumn = Schemas['BoardColumnOut']
export type LinkedPage = Schemas['LinkedPageOut']
export type Inspection = Schemas['InspectionOut']

/** One page of a list endpoint: `next_cursor` is null on the last page. */
export interface Page<T> {
  items: T[]
  next_cursor?: string | null
}

/** A backend error: `{"error": {"code", "message", "trace_id"}}`, or a transport failure. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly traceId: string | null

  constructor(code: string, status: number, message?: string, traceId?: string | null) {
    super(message ?? code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.traceId = traceId ?? null
  }

  get isVersionConflict(): boolean {
    return this.status === 409 && this.code.endsWith('.version_conflict')
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; trace_id?: string }
}

// Who to tell when the session is gone; set once by the router (see app/router).
let unauthorizedHandler: (() => void) | null = null

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

// A 401 from these is an answer, not a lost session.
const SESSION_PATHS = ['/api/auth/login', '/api/auth/me', '/api/auth/logout']

const sessionGuard: Middleware = {
  onResponse({ response, request }) {
    const path = new URL(request.url).pathname
    if (response.status === 401 && !SESSION_PATHS.includes(path)) unauthorizedHandler?.()
    return undefined
  },
}

/** The typed client. `X-Requested-With: herd` is the CSRF header the backend requires. */
export const api = createClient<paths>({
  // An absolute origin, so the client also works under jsdom (Request needs a full URL).
  baseUrl: globalThis.location?.origin ?? 'http://localhost',
  credentials: 'include',
  headers: { 'X-Requested-With': 'herd' },
  // Resolved at call time, so test doubles are honoured.
  fetch: (request) => globalThis.fetch(request),
})
api.use(sessionGuard)

/** Data, or an ApiError carrying the backend's code, message and trace id. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const body = (result.error ?? {}) as ErrorBody
    throw new ApiError(
      body.error?.code ?? `http.${result.response.status}`,
      result.response.status,
      body.error?.message,
      body.error?.trace_id,
    )
  }
  return result.data as T
}
