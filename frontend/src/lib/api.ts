import createClient, { type Middleware } from 'openapi-fetch'
import type { components, paths } from './api-types'
import { retryingOnConflict } from './retry'

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
export type Sprint = Schemas['SprintOut']
export type MyBoard = Schemas['MyBoardOut']
export type MyCard = Schemas['MyCardOut']
export type BoardRow = Schemas['BoardRowOut']
export type BoardCell = Schemas['BoardCellOut']
export type Inspection = Schemas['InspectionOut']

/** One page of a list endpoint: `next_cursor` is null on the last page. */
export interface Page<T> {
  items: T[]
  next_cursor?: string | null
}

/** A backend error: `{"error": {"code", "message", "trace_id", "details"?}}`, or a
 *  transport failure. `details` is data the client acts on (e.g. the merge of a
 *  proposal whose page moved on). */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly traceId: string | null
  readonly details: Record<string, unknown> | null

  constructor(
    code: string,
    status: number,
    message?: string,
    traceId?: string | null,
    details?: Record<string, unknown> | null,
  ) {
    super(message ?? code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.traceId = traceId ?? null
    this.details = details ?? null
  }

  /** `<area>.version_conflict`, or a named one such as `ai.connection_version_conflict`. */
  get isVersionConflict(): boolean {
    return this.status === 409 && /[._]version_conflict$/.test(this.code)
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; trace_id?: string; details?: unknown }
}

// Who to tell when the session is gone; set once by the router (see app/router).
let unauthorizedHandler: (() => void) | null = null

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

// A 401 from these is an answer, not a lost session.
const SESSION_PATHS = [
  '/api/auth/login',
  '/api/auth/login/second-factor',
  '/api/auth/me',
  '/api/auth/logout',
]

// Who to tell when the installation is in maintenance (503 `maintenance.active`).
let maintenanceHandler: (() => void) | null = null

export function onMaintenance(handler: (() => void) | null): void {
  maintenanceHandler = handler
}

async function inMaintenance(response: Response): Promise<boolean> {
  try {
    const body = (await response.clone().json()) as ErrorBody
    return body.error?.code === 'maintenance.active'
  } catch {
    return false
  }
}

const sessionGuard: Middleware = {
  async onResponse({ response, request }) {
    const path = new URL(request.url).pathname
    if (response.status === 401 && !SESSION_PATHS.includes(path)) unauthorizedHandler?.()
    if (response.status === 503 && maintenanceHandler && (await inMaintenance(response))) {
      maintenanceHandler()
    }
    return undefined
  },
}

/** The typed client. `X-Requested-With: herd` is the CSRF header the backend requires. */
export const api = createClient<paths>({
  // An absolute origin, so the client also works under jsdom (Request needs a full URL).
  baseUrl: globalThis.location?.origin ?? 'http://localhost',
  credentials: 'include',
  headers: { 'X-Requested-With': 'herd' },
  // Resolved at call time, so test doubles are honoured. A 409 `conflict.retry` is
  // sent once more after its `Retry-After` (at most 2 s, `retry.ts`).
  fetch: retryingOnConflict((request) => globalThis.fetch(request)),
})
api.use(sessionGuard)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Data, or an ApiError carrying the backend's code, message and trace id. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const body = (result.error ?? {}) as ErrorBody
    throw new ApiError(
      body.error?.code ?? `http.${result.response.status}`,
      result.response.status,
      body.error?.message,
      body.error?.trace_id,
      isRecord(body.error?.details) ? body.error.details : null,
    )
  }
  return result.data as T
}
