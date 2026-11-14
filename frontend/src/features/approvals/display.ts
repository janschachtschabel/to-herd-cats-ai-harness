import type { Message } from '@/lib/api'
import type { Approval, Question } from './queries'

/** What a release card shows: waiting; approved and still to run, run, or not run
 *  because the object changed meanwhile (`stale`); rejected; expired. */
export type ApprovalView = 'pending' | 'approved' | 'done' | 'stale' | 'rejected' | 'expired'

function expired(card: { state: string; expires_at: string }, now: number): boolean {
  return (
    card.state === 'expired' || (card.state === 'pending' && Date.parse(card.expires_at) <= now)
  )
}

/**
 * A release's state as the card shows it. After an approval the API's `outcome` tells
 * what became of the call: `stale` (the object changed since the person released it,
 * so nothing ran) or `ran`. Without one yet it is "approved".
 */
export function approvalView(approval: Approval, now: number): ApprovalView {
  if (expired(approval, now)) return 'expired'
  if (approval.state === 'pending') return 'pending'
  if (approval.state === 'rejected') return 'rejected'
  if (approval.outcome === 'stale') return 'stale'
  return approval.outcome === 'ran' ? 'done' : 'approved'
}

/** Whether the person asked can still decide here (the server checks again). */
export function mayDecide(approval: Approval, meId: string | undefined, now: number): boolean {
  return approval.addressed_to === meId && approvalView(approval, now) === 'pending'
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
