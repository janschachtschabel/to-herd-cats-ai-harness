import { describe, expect, test } from 'vitest'
import { makeApproval, makeQuestion } from '@/test/runs'
import { approvalView, mayDecide, questionView, subjectsOf } from './display'

const NOW = Date.parse('2026-11-15T00:00:00Z')

describe("a release card's state", () => {
  test('pending until decided or past its time', () => {
    expect(approvalView(makeApproval(), NOW)).toBe('pending')
    expect(approvalView(makeApproval({ expires_at: '2026-11-14T00:00:00Z' }), NOW)).toBe('expired')
    expect(approvalView(makeApproval({ state: 'expired' }), NOW)).toBe('expired')
    expect(approvalView(makeApproval({ state: 'rejected' }), NOW)).toBe('rejected')
  })

  test('after an approval the API tells whether the call ran or was stale', () => {
    const approved = makeApproval({ state: 'approved' })
    expect(approvalView(approved, NOW)).toBe('approved')
    expect(approvalView({ ...approved, outcome: 'ran' }, NOW)).toBe('done')
    expect(approvalView({ ...approved, outcome: 'stale' }, NOW)).toBe('stale')
    expect(approvalView({ ...approved, outcome: 'failed' }, NOW)).toBe('failed')
  })

  test('only the person asked decides, and only while it waits', () => {
    expect(mayDecide(makeApproval({ addressed_to: 'me' }), 'me', NOW)).toBe(true)
    expect(mayDecide(makeApproval({ addressed_to: 'me' }), 'other', NOW)).toBe(false)
    expect(mayDecide(makeApproval({ addressed_to: 'me', state: 'approved' }), 'me', NOW)).toBe(
      false,
    )
  })

  test('a question waits, is answered, or expires', () => {
    expect(questionView(makeQuestion(), NOW)).toBe('pending')
    expect(questionView(makeQuestion({ state: 'answered' }), NOW)).toBe('answered')
    expect(questionView(makeQuestion({ expires_at: '2026-11-14T00:00:00Z' }), NOW)).toBe('expired')
  })
})

describe('what a call would change', () => {
  const page = '00000000-0000-7000-8000-000000000a01'
  test("from the call's arguments, or else from the server's summary", () => {
    expect(subjectsOf({ args: { page_id: page, key: 'HC-12' }, summary: '' })).toEqual({
      pageId: page,
      ticketNumber: 12,
    })
    expect(
      subjectsOf({ args: null, summary: `link_ticket_page: key=HC-3, page_id=${page}` }),
    ).toEqual({ pageId: page, ticketNumber: 3 })
    expect(subjectsOf({ args: null, summary: 'post_message: conversation_id=x' })).toEqual({
      pageId: null,
      ticketNumber: null,
    })
    expect(subjectsOf({ args: { page_id: 'not-an-id' }, summary: '' }).pageId).toBeNull()
  })
})
