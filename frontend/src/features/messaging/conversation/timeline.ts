import type { Message } from '@/lib/api'
import type { PendingMessage } from './pending'

export type TimelineRow =
  | { kind: 'day'; key: string; date: string }
  | { kind: 'new'; key: 'new' }
  /** Where the person started her DM with an agent afresh (`fresh_start_at`). */
  | { kind: 'fresh'; key: 'fresh'; at: string }
  | { kind: 'message'; key: string; message: Message }
  | { kind: 'pending'; key: string; pending: PendingMessage }

/** The reader's calendar day of a timestamp (local time), e.g. "2026-11-13". */
export function dayKey(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Whether a message counts as unread for its reader, as the server counts: someone
 *  else's, written by a person, not deleted. */
export function countsAsUnread(message: Message, meId: string | undefined): boolean {
  return message.kind === 'human' && !message.deleted_at && message.author?.id !== meId
}

/**
 * The oldest unread message, from the unread count the server gave when the
 * conversation was opened: walking back from the newest, the `unread`-th message that
 * counts. With fewer loaded, the oldest loaded one that counts.
 */
export function firstUnreadId(
  newestFirst: readonly Message[],
  unread: number,
  meId: string | undefined,
): string | null {
  if (unread <= 0) return null
  let seen = 0
  let last: string | null = null
  for (const message of newestFirst) {
    if (!countsAsUnread(message, meId)) continue
    seen += 1
    last = message.id
    if (seen === unread) break
  }
  return last
}

/** Where one has read up to: the message and when it was written. */
export interface ReadMark {
  id: string
  at: string
}

/**
 * The oldest unread message after the read position: walking back from the newest
 * until the read message (or one written no later than it, should it be gone or not
 * loaded), the last message that counts.
 */
export function firstAfterPosition(
  newestFirst: readonly Message[],
  position: ReadMark,
  meId: string | undefined,
): string | null {
  const readAt = Date.parse(position.at)
  let last: string | null = null
  for (const message of newestFirst) {
    if (message.id === position.id || Date.parse(message.created_at) <= readAt) break
    if (countsAsUnread(message, meId)) last = message.id
  }
  return last
}

/** The rows of a conversation, oldest first: day separators, the "new" marker before
 *  `newBefore`, the fresh start before the first message after `freshStart` (at the
 *  end if none came yet), then the messages still on their way (those the server
 *  already has, by their client key, are left out). */
export function buildTimeline(
  newestFirst: readonly Message[],
  pending: readonly PendingMessage[],
  newBefore: string | null,
  freshStart: string | null = null,
): TimelineRow[] {
  const sent = new Set(newestFirst.map((m) => m.client_id).filter(Boolean))
  const rows: TimelineRow[] = []
  let day = ''
  const dayRow = (iso: string) => {
    const key = dayKey(iso)
    if (key === day) return
    day = key
    rows.push({ kind: 'day', key: `day-${key}`, date: iso })
  }
  let fresh = freshStart
  const freshRow = () => {
    if (fresh === null) return
    rows.push({ kind: 'fresh', key: 'fresh', at: fresh })
    fresh = null
  }
  for (let i = newestFirst.length - 1; i >= 0; i--) {
    const message = newestFirst[i]!
    if (fresh !== null && Date.parse(message.created_at) > Date.parse(fresh)) freshRow()
    dayRow(message.created_at)
    if (message.id === newBefore) rows.push({ kind: 'new', key: 'new' })
    rows.push({ kind: 'message', key: message.id, message })
  }
  freshRow()
  for (const entry of pending) {
    if (sent.has(entry.clientId)) continue
    dayRow(entry.createdAt)
    rows.push({ kind: 'pending', key: `pending-${entry.clientId}`, pending: entry })
  }
  return rows
}
