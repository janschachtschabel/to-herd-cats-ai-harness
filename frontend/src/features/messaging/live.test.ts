import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, test, vi } from 'vitest'
import type { LiveEvent } from '@/lib/live'
import { userKeys } from '@/features/admin/users/queries'
import { agentKeys } from '@/features/agents/keys'
import { approvalKeys } from '@/features/approvals/queries'
import { automationKeys } from '@/features/automations/queries'
import { calendarKeys } from '@/features/calendars/keys'
import { skillProposalKeys } from '@/features/skills/proposals/queries'
import { skillKeys } from '@/features/skills/queries'
import { ticketKeys } from '@/features/tickets/keys'
import { activityKeys, messagingKeys } from './keys'
import { COALESCE_MS, createCoalescer, invalidateFor } from './live'

const KEYS = {
  channels: messagingKeys.channels,
  dms: messagingKeys.dms,
  unread: messagingKeys.unread,
  conversationA: messagingKeys.conversation('a'),
  messagesA: [...messagingKeys.messages('a'), { includeSystem: true }],
  messagesB: [...messagingKeys.messages('b'), { includeSystem: true }],
  repliesA: messagingKeys.replies('a', 'p'),
  messageA: messagingKeys.message('a', 'p'),
  readPositionA: messagingKeys.readPosition('a'),
  pageThread: messagingKeys.pageThread('page'),
  activity: activityKeys.list(false),
  activityCount: activityKeys.count,
  spaces: ['spaces', 'sidebar'],
  wiki: ['wiki', 'page', 'x'],
  ticketList: ticketKeys.list({ assignee: 'me' }),
  ticket: ticketKeys.detail(42),
  ticketCounts: ticketKeys.counts,
  board: ticketKeys.board('space'),
  pageTickets: ticketKeys.pageTickets('page'),
  spaceList: ticketKeys.list({ who: 'all', space: 'space' }),
  otherSpaceList: ticketKeys.list({ who: 'all', space: 'other' }),
  otherTicket: ticketKeys.detail(7),
  otherBoard: ticketKeys.board('other'),
  column: ticketKeys.column('space', 'status', {}),
  epics: ticketKeys.epics('space'),
  otherEpics: ticketKeys.epics('other'),
  children: ticketKeys.children('parent'),
  statuses: ticketKeys.statuses('space'),
  ticketThread: ticketKeys.thread(42),
  sprints: [...ticketKeys.sprints('space'), 'choices'],
  otherSprints: [...ticketKeys.sprints('other'), 'choices'],
  myBoard: ticketKeys.myBoard,
  myColumn: ticketKeys.myColumn('review'),
  runA: agentKeys.run('run-a'),
  runB: agentKeys.run('run-b'),
  approval: approvalKeys.detail('ap-1'),
  question: approvalKeys.question('q-1'),
  myApprovals: [...approvalKeys.mine, 'pending'],
  skillProposals: skillProposalKeys.list({ state: 'open' }),
  skillProposal: skillProposalKeys.detail('sp-1'),
  skills: skillKeys.list({}),
  automationsMine: automationKeys.mine,
  automationsSpace: automationKeys.space('space'),
  automationA: automationKeys.detail('au-a'),
  firingsA: automationKeys.firings('au-a'),
  automationB: automationKeys.detail('au-b'),
  preview: automationKeys.preview(null),
  pendingUsers: [...userKeys.all, 'pending'],
  pendingCount: userKeys.pendingCount,
  calendars: [...calendarKeys.all, 'list'],
  calendarWindow: [...calendarKeys.all, 'window', {}],
}

/** What the ticket queries hold where the invalidation reads it (the ticket's id). */
const DATA: Partial<Record<keyof typeof KEYS, object>> = {
  ticket: { id: 't', number: 42 },
  otherTicket: { id: 'u', number: 7 },
}

/** A client holding every key above, fresh; returns which keys an event made stale. */
function staleAfter(event: Partial<LiveEvent> & Pick<LiveEvent, 'type'>): string[] {
  const client = new QueryClient()
  for (const [name, key] of Object.entries(KEYS))
    client.setQueryData(key, DATA[name as keyof typeof KEYS] ?? { items: [] })
  invalidateFor(client, {
    conversationId: null,
    messageId: null,
    parentId: null,
    ticketId: null,
    spaceId: null,
    ...event,
  })
  return Object.entries(KEYS)
    .filter(([, key]) => client.getQueryState(key)?.isInvalidated)
    .map(([name]) => name)
}

describe('live invalidation', () => {
  const ALL_TICKETS = [
    'ticketList',
    'ticket',
    'ticketCounts',
    'board',
    'pageTickets',
    'spaceList',
    'otherSpaceList',
    'otherTicket',
    'otherBoard',
    'column',
    'epics',
    'otherEpics',
    'children',
    'statuses',
    'ticketThread',
    'sprints',
    'otherSprints',
    'myBoard',
    'myColumn',
  ]

  test('resync refreshes every conversation, counter and activity query, nothing else', () => {
    expect(staleAfter({ type: 'resync' })).toEqual([
      'channels',
      'dms',
      'unread',
      'conversationA',
      'messagesA',
      'messagesB',
      'repliesA',
      'messageA',
      'readPositionA',
      'pageThread',
      'activity',
      'activityCount',
      ...ALL_TICKETS,
      'runA',
      'runB',
      'approval',
      'question',
      'myApprovals',
      'skillProposals',
      'skillProposal',
      'automationsMine',
      'automationsSpace',
      'automationA',
      'firingsA',
      'automationB',
      'calendars',
      'calendarWindow',
    ])
  })

  test('a changed automation refreshes every automation list, it and its log (plan M7)', () => {
    expect(staleAfter({ type: 'automation.changed', automationId: 'au-a' })).toEqual([
      'automationsMine',
      'automationsSpace',
      'automationA',
      'firingsA',
    ])
  })

  test('a skill proposal made or decided refreshes the proposals and the skills', () => {
    expect(staleAfter({ type: 'skill_proposal.changed', proposalId: 'sp-1' })).toEqual([
      'skillProposals',
      'skillProposal',
      'skills',
    ])
  })

  test("a decided card refreshes the cards, the runs and its conversation's messages", () => {
    expect(staleAfter({ type: 'card.changed', conversationId: 'a', messageId: 'm' })).toEqual([
      'messagesA',
      'repliesA',
      'runA',
      'runB',
      'approval',
      'question',
      'myApprovals',
    ])
    // A new card's activity entry refreshes my list of releases (and its count); an
    // account awaiting approval the people administration's lists and its count.
    expect(staleAfter({ type: 'notification.created' })).toEqual([
      'activity',
      'activityCount',
      'myApprovals',
      'pendingUsers',
      'pendingCount',
    ])
  })

  test("an agent run's progress refreshes that run only; the run's answer every run (plan M5)", () => {
    expect(
      staleAfter({ type: 'run.progress', conversationId: 'a', runId: 'run-a', step: 1 }),
    ).toEqual(['runA'])
    expect(staleAfter({ type: 'message.created', conversationId: 'a' })).toContain('runB')
    expect(staleAfter({ type: 'message.updated', conversationId: 'a' })).not.toContain('runA')
  })

  test('a ticket event refreshes that ticket and the views of its space only (review M4 P4)', () => {
    const affected = [
      'ticketList', // "my tickets" spans every space
      'ticket',
      'ticketCounts',
      'board',
      'pageTickets',
      'spaceList',
      'column',
      'epics',
      'children',
      'myBoard', // my board spans every space
      'myColumn',
    ]
    const event = { conversationId: 'a', ticketId: 't', spaceId: 'space' }
    expect(staleAfter({ type: 'ticket.updated', ...event })).toEqual(affected)
    expect(staleAfter({ type: 'ticket.created', ...event })).toEqual(affected)
  })

  test('a calendar event refreshes the calendar views, nothing else (plan M10)', () => {
    expect(staleAfter({ type: 'calendar.changed', spaceId: 'space' })).toEqual([
      'calendars',
      'calendarWindow',
    ])
  })

  test('a sprint event refreshes the sprints, boards and lists of its space (plan M4b)', () => {
    expect(staleAfter({ type: 'sprint.changed', spaceId: 'space' })).toEqual([
      'board',
      'spaceList',
      'column',
      'sprints',
    ])
    expect(staleAfter({ type: 'sprint.changed' })).toEqual(ALL_TICKETS)
  })

  test('a ticket event without its space refreshes every ticket view', () => {
    expect(staleAfter({ type: 'ticket.updated', conversationId: 'a', ticketId: 't' })).toEqual(
      ALL_TICKETS,
    )
  })

  test('a message refreshes its conversation (and thread), the counters, the DM list', () => {
    expect(staleAfter({ type: 'message.created', conversationId: 'a', parentId: 'p' })).toEqual([
      'dms',
      'unread',
      'messagesA',
      'repliesA',
      'messageA',
      // An agent's answer ends the run whose progress is shown.
      'runA',
      'runB',
    ])
  })

  test('the other events refresh only what they touch', () => {
    expect(staleAfter({ type: 'reaction.changed', conversationId: 'a' })).toEqual([
      'messagesA',
      'repliesA',
      'messageA',
    ])
    expect(staleAfter({ type: 'conversation.read', conversationId: 'a' })).toEqual([
      'unread',
      'readPositionA',
    ])
    expect(staleAfter({ type: 'channel.changed', conversationId: 'a' })).toEqual([
      'channels',
      'conversationA',
    ])
    expect(staleAfter({ type: 'notification.created', conversationId: 'a' })).toEqual([
      'activity',
      'activityCount',
      'myApprovals',
      'pendingUsers',
      'pendingCount',
    ])
    expect(staleAfter({ type: 'activity.changed' })).toEqual(['activity', 'activityCount'])
  })

  test('a changed access reloads everything shown; an inspection the conversation', () => {
    expect(staleAfter({ type: 'access.changed' })).toEqual(Object.keys(KEYS))
    expect(staleAfter({ type: 'dm.inspected', conversationId: 'a' })).toEqual(['conversationA'])
  })
})

describe('coalescing', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  test('a burst of events refreshes each query once per window', () => {
    vi.useFakeTimers()
    const client = new QueryClient()
    const spy = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
    const coalescer = createCoalescer(client)
    for (let i = 0; i < 20; i++) {
      coalescer.add({
        type: 'message.created',
        conversationId: 'a',
        messageId: `m${i}`,
        parentId: null,
        ticketId: null,
        spaceId: null,
      })
      coalescer.add({
        type: 'conversation.read',
        conversationId: 'a',
        messageId: null,
        parentId: null,
        ticketId: null,
        spaceId: null,
      })
    }
    expect(spy).not.toHaveBeenCalled()
    vi.advanceTimersByTime(COALESCE_MS)
    const keys = spy.mock.calls.map(([filters]) => JSON.stringify(filters?.queryKey))
    expect(keys.sort()).toEqual(
      [
        messagingKeys.dms,
        messagingKeys.unread,
        messagingKeys.readPosition('a'),
        messagingKeys.messages('a'),
        messagingKeys.message('a'),
        agentKeys.runs,
        agentKeys.allRunEvents,
      ]
        .map((key) => JSON.stringify(key))
        .sort(),
    )
    spy.mockClear()
    coalescer.add({
      type: 'activity.changed',
      conversationId: null,
      messageId: null,
      parentId: null,
      ticketId: null,
      spaceId: null,
    })
    vi.advanceTimersByTime(COALESCE_MS)
    expect(spy).toHaveBeenCalledTimes(1) // a new window after the last
    coalescer.add({
      type: 'activity.changed',
      conversationId: null,
      messageId: null,
      parentId: null,
      ticketId: null,
      spaceId: null,
    })
    coalescer.stop()
    vi.advanceTimersByTime(COALESCE_MS)
    expect(spy).toHaveBeenCalledTimes(1) // stopped: nothing more
  })
})
