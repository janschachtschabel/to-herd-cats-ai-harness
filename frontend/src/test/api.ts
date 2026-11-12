import { vi } from 'vitest'
import type { DirectoryEntry, Me, Page, Permission, Space, User } from '@/lib/api'

export interface Call {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
  headers: Headers
}

export interface Reply {
  status?: number
  body?: unknown
}

type Handler = (call: Call, params: Record<string, string>) => unknown

/**
 * Answers the app's fetches from `routes`, keyed "METHOD /api/path/:param". A handler
 * (or the route's plain value) is a Reply ({status, body}) or just the body (status
 * 200). Unmatched requests get
 * 404 `test.unmatched`. All calls are recorded.
 */
export function mockApi(routes: Record<string, Handler | object>) {
  const calls: Call[] = []
  const table = Object.entries(routes).map(([key, handler]) => {
    const [method, pattern] = key.split(' ') as [string, string]
    const names: string[] = []
    const regex = new RegExp(
      '^' + pattern.replace(/:(\w+)/g, (_, name: string) => (names.push(name), '([^/]+)')) + '$',
    )
    return { method, regex, names, handler }
  })

  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const request = new Request(input, init)
    const url = new URL(request.url)
    const text = request.method === 'GET' ? '' : await request.text()
    const call: Call = {
      method: request.method,
      path: url.pathname,
      query: url.searchParams,
      body: text ? JSON.parse(text) : undefined,
      headers: request.headers,
    }
    calls.push(call)
    for (const route of table) {
      const match = route.method === call.method && route.regex.exec(call.path)
      if (!match) continue
      const params = Object.fromEntries(route.names.map((n, i) => [n, match[i + 1] ?? '']))
      const result =
        typeof route.handler === 'function' ? await route.handler(call, params) : route.handler
      const reply: Reply = isReply(result) ? result : { body: result }
      return respond(reply.status ?? 200, reply.body)
    }
    return respond(404, { error: { code: 'test.unmatched', message: call.path, trace_id: '0' } })
  })
  return {
    calls,
    find: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  }
}

function isReply(value: unknown): value is Reply {
  return (
    typeof value === 'object' &&
    value !== null &&
    ('status' in value || 'body' in value) &&
    Object.keys(value).every((k) => k === 'status' || k === 'body')
  )
}

function respond(status: number, body: unknown): Response {
  if (status === 204 || body === undefined) return new Response(null, { status })
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function apiError(status: number, code: string, message = code): Reply {
  return {
    status,
    body: { error: { code, message, trace_id: '4bf92f3577b34da6a3ce929d0e0e4736' } },
  }
}

export function page<T>(items: T[], next_cursor: string | null = null): Page<T> {
  return { items, next_cursor }
}

export const ADMIN_PERMISSIONS: Permission[] = [
  'audit.read',
  'directory.read',
  'group.manage',
  'space.create',
  'user.manage',
]

let counter = 0
const id = () => `00000000-0000-7000-8000-${String(++counter).padStart(12, '0')}`

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: id(),
    email: 'lea@example.com',
    name: 'Lea Löwe',
    system_role: 'member',
    is_active: true,
    locale: 'de',
    last_login_at: null,
    version: 1,
    ...overrides,
  }
}

export function makeMe(permissions: Permission[], user: Partial<User> = {}): Me {
  return {
    user: makeUser({ email: 'me@example.com', name: 'Mia Muster', ...user }),
    org: { id: id(), name: 'Beispiel GmbH', slug: 'beispiel' },
    permissions,
  }
}

export function makeEntry(overrides: Partial<DirectoryEntry> = {}): DirectoryEntry {
  return { type: 'user', id: id(), name: 'Lea Löwe', ...overrides }
}

export function makeSpace(overrides: Partial<Space> = {}): Space {
  return {
    id: id(),
    kind: 'team',
    name: 'Projekt Apfel',
    slug: 'projekt-apfel',
    description: null,
    icon: null,
    owner_user_id: null,
    version: 1,
    my_role: 'admin',
    ...overrides,
  }
}
