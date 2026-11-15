import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { apiError, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { created, makeCall, makeToken } from '@/test/tokens'

const SECRET = 'herd_pat_wegwerf-nur-im-test-0000000000000000000'
const sales = makeSpace({ name: 'Vertrieb' })
const ops = makeSpace({ name: 'Betrieb' })

const shell = (permissions: Schemas['Action'][] = ['mcp.use']) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([sales, ops]),
})

describe('my access tokens', () => {
  test('without mcp.use there is no such page and no menu entry', async () => {
    mockApi({ ...shell(['directory.read']), 'GET /api/tokens': page([]) })
    const { user, router } = await renderApp('/')
    await user.click(await screen.findByRole('button', { name: 'Menü von Mia Muster' }))
    expect(await screen.findByRole('menuitem', { name: /Profil/ })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Zugangstoken' })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    await router.navigate({ to: '/profile/tokens' })
    expect(await screen.findByText('Seite nicht gefunden')).toBeInTheDocument()
  })

  test('lists my tokens with mode, spaces, dates and state', async () => {
    mockApi({
      ...shell(),
      'GET /api/tokens': page([
        makeToken({ name: 'Laptop', mode: 'write', space_ids: [sales.id] }),
        makeToken({ name: 'Alt', revoked_at: '2026-11-12T08:00:00Z' }),
      ]),
    })
    const { user } = await renderApp('/')
    await user.click(await screen.findByRole('button', { name: 'Menü von Mia Muster' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Zugangstoken' }))
    const laptop = await screen.findByRole('article', { name: 'Laptop' })
    expect(within(laptop).getByText('Lesen und schreiben')).toBeInTheDocument()
    expect(within(laptop).getByText('Vertrieb')).toBeInTheDocument()
    expect(within(laptop).getByText('noch nie')).toBeInTheDocument()
    expect(within(laptop).getByText('Aktiv')).toBeInTheDocument()
    const old = screen.getByRole('article', { name: 'Alt' })
    expect(within(old).getByText('Alle meine Bereiche')).toBeInTheDocument()
    expect(within(old).getByText('Widerrufen')).toBeInTheDocument()
    expect(within(old).queryByRole('button', { name: 'Alt widerrufen' })).not.toBeInTheDocument()
  })

  test('creates a token and shows its clear text once, with how to connect a client', async () => {
    const made = makeToken({ name: 'Codex', mode: 'write', space_ids: [ops.id] })
    const api = mockApi({
      ...shell(),
      'GET /api/tokens': page([]),
      'POST /api/tokens': { status: 201, body: created(made, SECRET) },
    })
    const { user } = await renderApp('/profile/tokens')
    expect(await screen.findByText('Du hast noch kein Zugangstoken.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Token anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Zugangstoken anlegen' })
    await user.type(within(dialog).getByLabelText('Name'), 'Codex')
    await user.click(within(dialog).getByRole('radio', { name: /Lesen und schreiben/ }))
    await user.click(within(dialog).getByRole('radio', { name: 'Nur ausgewählte Bereiche' }))
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(
      await within(dialog).findByText('Bitte mindestens einen Bereich wählen.'),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('checkbox', { name: 'Betrieb' }))
    const days = within(dialog).getByLabelText('Gültig (Tage)')
    await user.clear(days)
    await user.type(days, '30')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/tokens')).toHaveLength(1))
    expect(api.find('POST', '/api/tokens')[0]!.body).toEqual({
      name: 'Codex',
      mode: 'write',
      expires_in_days: 30,
      space_ids: [ops.id],
    })

    const shown = await screen.findByRole('dialog', { name: 'Dein neues Token: Codex' })
    expect(within(shown).getByText(/nur dieses eine Mal angezeigt/)).toBeInTheDocument()
    expect(within(shown).getByLabelText('Token')).toHaveValue(SECRET)
    await user.click(within(shown).getByRole('button', { name: 'Token kopieren' }))
    expect(await navigator.clipboard.readText()).toBe(SECRET)
    expect(within(shown).getByRole('button', { name: 'Token kopieren' })).toHaveTextContent(
      'Kopiert',
    )
    const url = `${window.location.origin}/mcp`
    expect(
      within(shown).getByText(new RegExp(`claude mcp add --transport http herd ${url}`)),
    ).toBeInTheDocument()
    expect(within(shown).getByText(/Authorization: Bearer \$HERD_TOKEN/)).toBeInTheDocument()
    expect(within(shown).getByText(/bearer_token_env_var = "HERD_TOKEN"/)).toBeInTheDocument()
    await user.click(within(shown).getByRole('button', { name: 'Fertig' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(document.body).not.toHaveTextContent(SECRET)
  })

  test('a space the API refuses is put into words', async () => {
    mockApi({
      ...shell(),
      'GET /api/tokens': page([]),
      'POST /api/tokens': apiError(422, 'token.space_invalid'),
    })
    const { user } = await renderApp('/profile/tokens')
    await user.click(await screen.findByRole('button', { name: 'Token anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'X')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(
      await within(dialog).findByText(/Einen der Bereiche darfst du nicht \(mehr\) lesen/),
    ).toBeInTheDocument()
  })

  test('revokes after asking, and shows the recent calls of a token', async () => {
    const token = makeToken({ name: 'Laptop', last_used_at: '2026-11-15T09:30:00Z' })
    const api = mockApi({
      ...shell(),
      'GET /api/tokens': page([token]),
      [`GET /api/tokens/${token.id}/calls`]: page([
        makeCall({ tool: 'search_tickets', outcome: 'ok', duration_ms: 12 }),
        makeCall({ tool: 'set_ticket_status', outcome: 'refused' }),
      ]),
      [`DELETE /api/tokens/${token.id}`]: { status: 204 },
    })
    const { user } = await renderApp('/profile/tokens')
    await user.click(await screen.findByRole('button', { name: 'Aufrufe von Laptop' }))
    const calls = await screen.findByRole('dialog', { name: 'Aufrufe von Laptop' })
    expect(await within(calls).findByText('search_tickets')).toBeInTheDocument()
    expect(within(calls).getByText('12 ms')).toBeInTheDocument()
    expect(within(calls).getByText('Abgelehnt')).toBeInTheDocument()
    await user.keyboard('{Escape}')

    await user.click(screen.getByRole('button', { name: 'Laptop widerrufen' }))
    const confirm = await screen.findByRole('dialog', { name: 'Token widerrufen?' })
    expect(api.find('DELETE', `/api/tokens/${token.id}`)).toHaveLength(0)
    await user.click(within(confirm).getByRole('button', { name: 'Widerrufen' }))
    await waitFor(() => expect(api.find('DELETE', `/api/tokens/${token.id}`)).toHaveLength(1))
  })
})
