import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import i18n, { setLocale, type Locale } from '@/lib/i18n'
import { ADMIN_PERMISSIONS, makeMe, makeSpace, makeUser, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

const KEY_LIKE =
  /\b(app|common|actions|states|forms|validation|errors|notFound|auth|nav|userMenu|roles|systemRoles|principals|spaces|users|groups|audit)\.[\w.]+/

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

function api() {
  mockApi({
    'GET /api/auth/me': me,
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
  '/admin/users',
  '/admin/groups',
  '/admin/groups/g1',
  '/admin/audit',
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

  test.each<Locale>(['de', 'en'])('every user-facing string resolves in %s', async (locale) => {
    setLocale(locale)
    api()
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
  })
})
