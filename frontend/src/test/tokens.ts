import type { Schemas } from '@/lib/api'

type Token = Schemas['TokenOut']
type AdminToken = Schemas['AdminTokenOut']
type Call = Schemas['McpCallOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-9${String(++counter).padStart(11, '0')}`

export function makeToken(overrides: Partial<Token> = {}): Token {
  return {
    id: id(),
    kind: 'personal',
    agent_id: null,
    name: 'Claude Code Laptop',
    mode: 'read',
    space_ids: null,
    created_at: '2026-11-10T08:00:00Z',
    expires_at: '2099-02-08T08:00:00Z',
    last_used_at: null,
    revoked_at: null,
    ...overrides,
  }
}

export function makeAdminToken(overrides: Partial<AdminToken> = {}): AdminToken {
  return {
    ...makeToken(),
    user: { id: id(), name: 'Lea Löwe' },
    agent: null,
    ...overrides,
  }
}

export function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: id(),
    tool: 'search',
    outcome: 'ok',
    duration_ms: 42,
    created_at: '2026-11-15T09:30:00Z',
    ...overrides,
  }
}

/** The answer to creating a token: its metadata and the clear text, this once. */
export function created(token: Token, secret: string): Schemas['TokenCreatedOut'] {
  return { ...token, secret }
}
