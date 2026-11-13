import { screen, within } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { ADMIN_PERMISSIONS, type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { NAV_SECTIONS, visibleSections } from './nav'

function sections(): string[] {
  const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
  return [...nav.querySelectorAll('[data-section]')].map((s) => s.getAttribute('data-section')!)
}

describe('shell', () => {
  test('shell shows admin section only for admin/owner', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS), 'GET /api/spaces': page([]) })
    await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(within(nav).getByRole('heading', { name: 'Verwaltung' })).toBeInTheDocument()
    for (const name of ['Personen', 'Gruppen', 'Protokoll']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
    }
  })

  test('a member sees no administration', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(['space.create']), 'GET /api/spaces': page([]) })
    await renderApp('/spaces')
    expect(sections()).toEqual(['activity', 'search', 'channels', 'direct', 'spaces', 'work'])
    expect(screen.queryByText('Verwaltung')).not.toBeInTheDocument()
  })

  test('only the administration pages one may open are listed', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(['audit.read']), 'GET /api/spaces': page([]) })
    await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(within(nav).getByRole('link', { name: 'Protokoll' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'Personen' })).not.toBeInTheDocument()
  })

  test('shell hides sections of later milestones', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS), 'GET /api/spaces': page([]) })
    await renderApp('/spaces')
    expect(sections()).toEqual([
      'activity',
      'search',
      'channels',
      'direct',
      'spaces',
      'work',
      'admin',
    ])
    expect(screen.getByText('Arbeit')).toBeInTheDocument()
    // The filter, not the absence of renderers, decides: before M4 "work" is out.
    const me = makeMe(ADMIN_PERMISSIONS)
    expect(visibleSections(me, 1).map((s) => s.id)).toEqual(['spaces', 'admin'])
    expect(visibleSections(me, 3).map((s) => s.id)).not.toContain('work')
    expect(visibleSections(me, 4).map((s) => s.id)).toEqual(
      NAV_SECTIONS.filter((s) => s.milestone <= 4).map((s) => s.id),
    )
  })

  test('the sidebar lists open and team spaces and my own space, not those of others', async () => {
    const me = makeMe(ADMIN_PERMISSIONS)
    mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': page([
        makeSpace({ kind: 'personal', name: 'Mia Muster', owner_user_id: me.user.id }),
        makeSpace({ kind: 'personal', name: 'Jan Jansen', owner_user_id: 'someone-else' }),
        makeSpace({ kind: 'open', name: 'Handbuch' }),
        makeSpace({ kind: 'team', name: 'Team Dienste' }),
      ]),
    })
    await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    const links = within(nav.querySelector('[data-section="spaces"]') as HTMLElement)
      .findAllByRole('link')
      .then((all) => all.map((a) => a.textContent))
    expect(await links).toEqual(['Bereiche', 'Handbuch', 'Team Dienste', 'Mein Bereich'])
  })

  test('the sidebar asks for its own spaces only and offers the rest page by page', async () => {
    const me = makeMe(ADMIN_PERMISSIONS)
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': (call: Call) =>
        call.query.get('cursor') === 'next'
          ? page([makeSpace({ kind: 'team', name: 'Team Später' })])
          : page([makeSpace({ kind: 'open', name: 'Handbuch' })], 'next'),
    })
    const { user } = await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    const spaces = nav.querySelector('[data-section="spaces"]') as HTMLElement
    await within(spaces).findByRole('link', { name: 'Handbuch' })
    const sidebarCalls = api
      .find('GET', '/api/spaces')
      .filter((c) => c.query.get('include_others_personal') === 'false')
    expect(sidebarCalls.length).toBeGreaterThan(0)
    await user.click(within(spaces).getByRole('button', { name: 'Weitere Bereiche' }))
    expect(await within(spaces).findByRole('link', { name: 'Team Später' })).toBeInTheDocument()
    expect(within(spaces).queryByRole('button', { name: 'Weitere Bereiche' })).toBeNull()
  })

  test('the user menu switches the theme', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(['space.create']), 'GET /api/spaces': page([]) })
    const { user } = await renderApp('/spaces')
    await user.click(screen.getByRole('button', { name: 'Menü von Mia Muster' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'Dunkel' }))
    expect(document.documentElement).toHaveClass('dark')
  })

  test('on a narrow screen the sidebar starts closed, opens over the page and closes again', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query.includes('max-width'),
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
        }) as unknown as MediaQueryList,
    )
    mockApi({ 'GET /api/auth/me': makeMe(['space.create']), 'GET /api/spaces': page([]) })
    const { user } = await renderApp('/spaces')
    const toggle = screen.getByRole('button', { name: 'Seitenleiste ein- oder ausblenden' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('navigation', { name: 'Hauptnavigation' })).toBeNull()
    await user.click(toggle)
    expect(screen.getByRole('navigation', { name: 'Hauptnavigation' })).toBeVisible()
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    await user.click(
      within(screen.getByRole('navigation', { name: 'Hauptnavigation' })).getByRole('link', {
        name: 'Aktivität',
      }),
    )
    expect(toggle).toHaveAttribute('aria-expanded', 'false') // a link was followed
    expect(screen.queryByRole('navigation', { name: 'Hauptnavigation' })).toBeNull()
  })
})
