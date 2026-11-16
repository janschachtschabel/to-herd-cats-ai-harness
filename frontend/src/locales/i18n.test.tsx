import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import i18n, { setLocale, type Locale } from '@/lib/i18n'
import {
  ADMIN_PERMISSIONS,
  makeAttachment,
  makeMe,
  makePage,
  makeSpace,
  makeTag,
  makeUser,
  makeVersion,
  mockApi,
  nodeOf,
  page,
} from '@/test/api'
import { renderApp } from '@/test/render'
import { makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'

const KEY_LIKE =
  /\b(app|common|actions|states|forms|validation|errors|notFound|auth|nav|userMenu|profile|roles|systemRoles|principals|spaces|users|groups|audit|wiki|search|tickets)\.[\w.]+/

/** What a person reads, text node by text node, and the accessible labels; scripts
 *  (next-themes injects one) left out. */
function visibleTexts(): string[] {
  const texts: string[] = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.parentElement?.closest('script, style')) continue
    texts.push(node.textContent ?? '')
  }
  document.body.querySelectorAll('[aria-label]').forEach((el) => {
    texts.push(el.getAttribute('aria-label') ?? '')
  })
  return texts
}

const me = makeMe(ADMIN_PERMISSIONS)
const team = makeSpace({ name: 'Team Dienste' })
const group = { id: 'g1', name: 'Redaktion', description: null, version: 1 }
const tag = makeTag()
const handbook = makePage({
  space_id: team.id,
  status: 'draft',
  tags: [tag.id],
  created_by: { type: 'user', id: me.user.id },
  content_md: '# Handbuch\n\n## Urlaub\n\nSiehe [[Fehlt]].',
})

function api(locale: Locale) {
  mockApi({
    // The interface speaks the person's stored language.
    'GET /api/auth/me': { ...me, user: { ...me.user, locale } },
    'GET /api/auth/me/totp': {
      enabled_at: '2026-11-16T12:00:00Z',
      recovery_codes_left: 3,
      unavailable: null,
    },
    'GET /api/spaces': page([
      makeSpace({ kind: 'open', name: 'Handbuch', my_role: 'viewer' }),
      team,
      makeSpace({ kind: 'personal', name: 'Mia', owner_user_id: me.user.id }),
    ]),
    'GET /api/spaces/:id': team,
    'GET /api/spaces/:id/members': page([
      { member_type: 'user', member_id: me.user.id, role: 'admin', name: 'Mia Muster' },
      { member_type: 'group', member_id: 'g1', role: 'editor', name: 'Redaktion' },
    ]),
    'GET /api/spaces/:id/pages/tree': page([nodeOf(handbook)]),
    'GET /api/spaces/:id/pages/by-path': handbook,
    'GET /api/spaces/:id/trash': page([
      { ...nodeOf(makePage({ title: 'Alt' })), trashed_at: '2026-11-12T11:00:00Z' },
    ]),
    'GET /api/tags': page([tag]),
    'GET /api/pages/:id/attachments': page([makeAttachment()]),
    'GET /api/pages/:id/versions': page([makeVersion(2, { source: 'collab' }), makeVersion(1)]),
    'GET /api/pages/:id/diff': {
      from_number: 1,
      to_number: 2,
      from_title: 'Handbuch',
      to_title: 'Handbuch',
      title_changed: false,
      hunks: [
        { kind: 'equal', lines: ['# Handbuch'] },
        { kind: 'insert', lines: ['neu'] },
      ],
    },
    'GET /api/pages/:id/tickets': page([makeTicketSummary()]),
    'GET /api/spaces/:id/ticket-statuses': page(STATUSES),
    'GET /api/tickets/counts': { assigned_open: 3 },
    'GET /api/tickets': page([
      makeTicketSummary({ assignee: { type: 'user', id: me.user.id, name: 'Mia Muster' } }),
    ]),
    'GET /api/spaces/:id/epics': page([
      {
        ...makeTicketSummary({ number: 7, kind: 'epic' }),
        children: { open: 1, active: 0, review: 0, done: 1, cancelled: 0 },
      },
    ]),
    'GET /api/spaces/:id/board': {
      columns: STATUSES.map((status, i) => ({
        status: statusRef(status),
        count: i === 0 ? 1 : 0,
        items: i === 0 ? [makeTicketSummary()] : [],
        next_cursor: null,
      })),
    },
    'GET /api/admin/users': page([makeUser(), makeUser({ is_active: false, name: 'Jan' })]),
    'GET /api/admin/groups': page([group]),
    'GET /api/admin/groups/:id': group,
    'GET /api/admin/groups/:id/members': page([
      { member_type: 'user', member_id: 'u', name: 'Lea' },
    ]),
    'GET /api/admin/audit': page([
      {
        id: 'a1',
        actor_type: 'user',
        actor_id: me.user.id,
        actor_name: 'Mia Muster',
        action: 'space.member_set',
        target_type: 'space',
        target_id: team.id,
        details: { member_type: 'group', member_id: 'g1', role: 'editor' },
        ip: '127.0.0.1',
        created_at: '2026-11-12T10:00:00Z',
      },
    ]),
  })
}

const PAGES = [
  '/spaces',
  `/spaces/${team.id}`,
  `/spaces/${team.id}/settings`,
  `/spaces/${team.id}/trash`,
  `/spaces/${team.id}/p/handbuch`,
  `/spaces/${team.id}/p/handbuch?view=versions`,
  `/spaces/${team.id}/p/handbuch?view=edit`,
  `/spaces/${team.id}/board`,
  `/spaces/${team.id}/epics`,
  '/tickets',
  '/admin/users',
  '/admin/groups',
  '/admin/groups/g1',
  '/admin/audit',
  '/profile',
]

describe('translations', () => {
  const missing: string[] = []
  beforeEach(() => {
    missing.length = 0
    i18n.options.saveMissing = true
    i18n.options.missingKeyHandler = (_lngs, _ns, key) => void missing.push(key)
  })
  afterEach(() => {
    i18n.options.saveMissing = false
    i18n.options.missingKeyHandler = false
  })

  // Twenty routes rendered one after the other: give it room on a busy machine.
  test.each<Locale>(['de', 'en'])(
    'every user-facing string resolves in %s',
    { timeout: 30_000 },
    async (locale) => {
      setLocale(locale)
      api(locale)
      for (const path of PAGES) {
        const { user } = await renderApp(path)
        await screen.findByRole('heading', { level: 1 })
        const menu = locale === 'de' ? 'Menü von Mia Muster' : 'Menu of Mia Muster'
        await user.click(screen.getByRole('button', { name: menu }))
        await screen.findByRole('menu')
        expect(visibleTexts().filter((text) => KEY_LIKE.test(text))).toEqual([])
        cleanup()
      }
      expect(missing).toEqual([])
    },
  )
})
