import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { ADMIN_PERMISSIONS, makeMe, makeSpace, mockApi, page } from '@/test/api'
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
    expect(sections()).toEqual(['spaces'])
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
    expect(sections()).toEqual(['spaces', 'admin'])
    for (const text of ['Aktivität', 'Suche', 'Kanäle', 'Direkt', 'Arbeit']) {
      expect(screen.queryByText(text)).not.toBeInTheDocument()
    }
    // The filter, not the absence of renderers, decides: at M4 "work" is in.
    const me = makeMe(ADMIN_PERMISSIONS)
    expect(visibleSections(me, 1).map((s) => s.id)).toEqual(['spaces', 'admin'])
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

  test('the user menu switches language and theme', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(['space.create']), 'GET /api/spaces': page([]) })
    const { user } = await renderApp('/spaces')
    await user.click(screen.getByRole('button', { name: 'Menü von Mia Muster' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'English' }))
    expect(await screen.findByRole('heading', { name: 'Spaces', level: 1 })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')

    await user.click(screen.getByRole('button', { name: 'Menu of Mia Muster' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'Dark' }))
    expect(document.documentElement).toHaveClass('dark')
  })
})
