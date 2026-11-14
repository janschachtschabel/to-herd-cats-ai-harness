import type { RunEvent } from '@/features/agents/queries'
import type { Message } from '@/lib/api'
import type { Approval, Question } from './queries'

/** What a release card shows: waiting; approved and still to run, run, or not run
 *  because the object changed meanwhile (`stale`); rejected; expired. */
export type ApprovalView = 'pending' | 'approved' | 'done' | 'stale' | 'rejected' | 'expired'

const STALE = 'approval_stale'

function expired(card: { state: string; expires_at: string }, now: number): boolean {
  return (
    card.state === 'expired' || (card.state === 'pending' && Date.parse(card.expires_at) <= now)
  )
}

/**
 * A release's state as the card shows it. After an approval the run's journal tells
 * what became of the call (the tool call with the approval's step and call id): its
 * result `approval_stale` means the object changed since the person released it and
 * nothing ran; any other result means it ran. Without that entry yet (or without the
 * journal: a reader who may not read it) it is "approved".
 */
export function approvalView(
  approval: Approval,
  events: readonly RunEvent[] | undefined,
  now: number,
): ApprovalView {
  if (expired(approval, now)) return 'expired'
  if (approval.state === 'pending') return 'pending'
  if (approval.state === 'rejected') return 'rejected'
  const call = (events ?? []).find((event) => {
    if (event.kind !== 'tool_call' || event.redacted) return false
    const content = event.content as { step?: unknown; call_id?: unknown }
    return content.step === approval.step && content.call_id === approval.call_id
  })
  if (!call) return 'approved'
  const text = (call.content as { text?: unknown }).text
  return typeof text === 'string' && text.startsWith(STALE) ? 'stale' : 'done'
}

/** Whether the person asked can still decide here (the server checks again). */
export function mayDecide(approval: Approval, meId: string | undefined, now: number): boolean {
  return approval.addressed_to === meId && approvalView(approval, undefined, now) === 'pending'
}

export type QuestionView = 'pending' | 'answered' | 'expired'

export function questionView(question: Question, now: number): QuestionView {
  if (expired(question, now)) return 'expired'
  return question.state === 'answered' ? 'answered' : 'pending'
}

/** What a call would change, for links: a page and a ticket, from the call's
 *  arguments (the person asked) or else the server's summary (`tool: k=v, ...`). */
export interface Subjects {
  pageId: string | null
  ticketNumber: number | null
}

const UUID = /^[0-9a-fA-F-]{36}$/
const KEY = /^[A-Za-z]+-(\d{1,9})$/

export function subjectsOf(approval: Pick<Approval, 'args' | 'summary'>): Subjects {
  const named: Record<string, string> = {}
  if (approval.args) {
    for (const [key, value] of Object.entries(approval.args)) {
      if (typeof value === 'string') named[key] = value
    }
  } else {
    const list = approval.summary.split(': ').slice(1).join(': ')
    for (const part of list.split(', ')) {
      const at = part.indexOf('=')
      if (at > 0) named[part.slice(0, at)] = part.slice(at + 1)
    }
  }
  const page = named.page_id && UUID.test(named.page_id) ? named.page_id : null
  const key = named.key ? KEY.exec(named.key) : null
  return { pageId: page, ticketNumber: key ? Number(key[1]) : null }
}

/** The arguments worth reading beside the diff (a page's full new text is the diff). */
export function shownArgs(approval: Approval): Record<string, unknown> | null {
  if (!approval.args) return null
  const { content_md: _content, ...rest } = approval.args
  return approval.diff_url ? rest : approval.args
}

/** Whether a message is shown as a run's card. */
export function isCard(message: Message): boolean {
  return (
    message.card !== null &&
    message.card !== undefined &&
    (message.card.type === 'approval' || message.card.type === 'question')
  )
}
