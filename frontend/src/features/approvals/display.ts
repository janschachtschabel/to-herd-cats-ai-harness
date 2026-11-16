import type { Message } from '@/lib/api'
import type { Approval, Question } from './queries'

/** What a release card shows: waiting; approved and still to run, run, or not run
 *  because the object changed meanwhile (`stale`) or its step took too long and was
 *  undone (`failed`); rejected; expired. */
export type ApprovalView =
  'pending' | 'approved' | 'done' | 'stale' | 'failed' | 'rejected' | 'expired'

function expired(card: { state: string; expires_at: string }, now: number): boolean {
  return (
    card.state === 'expired' || (card.state === 'pending' && Date.parse(card.expires_at) <= now)
  )
}

/**
 * A release's state as the card shows it. After an approval the API's `outcome` tells
 * what became of the call: `stale` (the object changed since the person released it,
 * so nothing ran), `failed` (its step took too long and was undone) or `ran`. Without one yet it is "approved".
 */
export function approvalView(approval: Approval, now: number): ApprovalView {
  if (expired(approval, now)) return 'expired'
  if (approval.state === 'pending') return 'pending'
  if (approval.state === 'rejected') return 'rejected'
  if (approval.outcome === 'stale') return 'stale'
  if (approval.outcome === 'failed') return 'failed'
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
 *  arguments or else the server's summary (`tool: k=v, ...`); both are the person
 *  asked's alone, so anyone else gets none. */
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
  } else if (approval.summary !== null) {
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

/** An external tool's own name on a release card: the server names it in the summary
 *  ("<server> · <tool>"), for the person asked. Null for the catalog's tools, and for
 *  anyone else (the card's title then names the tool as the run does). */
export function externalToolOf(approval: Pick<Approval, 'external' | 'summary'>): string | null {
  if (!approval.external || approval.summary === null) return null
  const at = approval.summary.indexOf(' · ')
  return at >= 0 ? approval.summary.slice(at + 3) : approval.summary
}

/** Whether a message is shown as a run's card. */
export function isCard(message: Message): boolean {
  return (
    message.card !== null &&
    message.card !== undefined &&
    (message.card.type === 'approval' || message.card.type === 'question')
  )
}
