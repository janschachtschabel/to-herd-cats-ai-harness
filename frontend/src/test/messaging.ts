import type { ActivityEntry, Conversation, Message, MessageWrite, Me, Space } from '@/lib/api'
import { page } from './api'

let counter = 0
/** A UUID-shaped id, unique per call (search params accept only those). */
export const uid = () => `00000000-0000-7000-9000-${String(++counter).padStart(12, '0')}`

export function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: uid(),
    kind: 'channel',
    space_id: 'space-1',
    page_id: null,
    name: 'allgemein',
    topic: null,
    archived_at: null,
    created_by: null,
    created_at: '2026-11-13T08:00:00Z',
    version: 1,
    can_post: true,
    participants: [],
    inspections: [],
    ...overrides,
  }
}

export function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: uid(),
    conversation_id: 'c-1',
    parent_id: null,
    author: { type: 'user', id: 'someone', name: 'Lea Löwe' },
    kind: 'human',
    body_md: 'Hallo',
    client_id: null,
    created_at: '2026-11-13T09:00:00Z',
    edited_at: null,
    deleted_at: null,
    reply_count: 0,
    last_reply_at: null,
    mentions: [],
    reactions: [],
    system: null,
    ...overrides,
  }
}

export function written(message: Message, notNotified: string[] = []): MessageWrite {
  return { ...message, not_notified: notNotified }
}

export function makeActivity(overrides: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    id: uid(),
    reason: 'mention',
    created_at: '2026-11-13T09:00:00Z',
    read_at: null,
    done_at: null,
    conversation: {
      id: 'c-1',
      kind: 'channel',
      name: 'allgemein',
      space_id: 'space-1',
      page_id: null,
      ticket_number: null,
    },
    message_id: uid(),
    parent_id: null,
    author: { type: 'user', id: 'someone', name: 'Lea Löwe' },
    snippet: 'Hallo @[Mia Muster](user:00000000-0000-7000-8000-000000000001)',
    ...overrides,
  }
}

/** The routes every screen of the shell asks for, with nothing in them. */
export function shellRoutes(me: Me, spaces: Space[] = []) {
  return {
    'GET /api/auth/me': me,
    'GET /api/spaces': page(spaces),
    'GET /api/channels': page([]),
    'GET /api/dms': page([]),
    'GET /api/conversations/unread': page([]),
    'GET /api/activity/count': { open: 0, unread: 0 },
    'GET /api/tickets/counts': { assigned_open: 0 },
  }
}
