import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { ADMIN_PERMISSIONS, apiError, makeEntry, makeMe, mockApi, page } from '@/test/api'
import { makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

describe('direct message inspection', () => {
  test('without dm.inspect: no link, no page, no request', async () => {
    const api = mockApi(shellRoutes(makeMe(ADMIN_PERMISSIONS)))
    await renderApp('/admin/dm-inspect')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Einsicht in Direktnachrichten' })).toBeNull()
    expect(api.calls.filter((c) => c.path.startsWith('/api/admin/dm-inspect'))).toEqual([])
  })

  test('with dm.inspect: a person, a reason, then the messages read only until expiry', async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    const dm = {
      conversation_id: '00000000-0000-7000-a000-000000000001',
      participants: [
        { id: lea.id, name: 'Lea Löwe', is_active: true },
        { id: 'jan', name: 'Jan Jansen', is_active: true },
      ],
      created_at: '2026-11-13T08:00:00Z',
      last_message_at: '2026-11-13T09:00:00Z',
    }
    const expires = new Date(Date.now() + 60 * 60_000).toISOString()
    const api = mockApi({
      ...shellRoutes(makeMe(['dm.inspect', 'directory.read'])),
      'GET /api/directory': page([lea]),
      'GET /api/admin/dm-inspect': page([dm]),
      'POST /api/admin/dm-inspect': {
        status: 201,
        body: {
          id: 'grant-1',
          conversation_id: dm.conversation_id,
          reason: 'Verdacht auf Belästigung, Meldung 42',
          granted_at: new Date().toISOString(),
          expires_at: expires,
        },
      },
      'GET /api/admin/dm-inspect/:id/messages': page([
        makeMessage({
          body_md: 'Hallo **Jan**',
          author: { type: 'user', id: lea.id, name: 'Lea Löwe' },
        }),
      ]),
    })
    const { user } = await renderApp('/admin/dm-inspect')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(
      within(nav).getByRole('link', { name: 'Einsicht in Direktnachrichten' }),
    ).toBeInTheDocument()
    await user.click(await screen.findByRole('combobox', { name: 'Person' }))
    await user.click(await screen.findByRole('option', { name: /Lea Löwe/ }))
    await waitFor(() =>
      expect(api.find('GET', '/api/admin/dm-inspect')[0]?.query.get('user_id')).toBe(lea.id),
    )
    await user.click(await screen.findByRole('button', { name: 'Einsicht beantragen' }))
    const reason = screen.getByLabelText('Begründung')
    await user.type(reason, 'kurz')
    await user.click(screen.getByRole('button', { name: 'Einsicht beginnen' }))
    expect(await screen.findByText('Mindestens 10 Zeichen.')).toBeInTheDocument()
    expect(api.find('POST', '/api/admin/dm-inspect')).toEqual([])

    await user.clear(reason)
    await user.type(reason, 'Verdacht auf Belästigung, Meldung 42')
    await user.click(screen.getByRole('button', { name: 'Einsicht beginnen' }))
    expect(api.find('POST', '/api/admin/dm-inspect')[0]?.body).toEqual({
      conversation_id: dm.conversation_id,
      reason: 'Verdacht auf Belästigung, Meldung 42',
    })
    expect(await screen.findByText(/noch 60 Minuten/)).toBeInTheDocument()
    expect(await screen.findByText('Jan', { selector: 'strong' })).toBeInTheDocument()
    expect(screen.getByText('Begründung: Verdacht auf Belästigung, Meldung 42')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: /Nachricht/ })).toBeNull()
  })

  test("an agent's messages carry the AI mark; a stopped run says why", async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    const conversation = '00000000-0000-7000-a000-000000000003'
    mockApi({
      ...shellRoutes(makeMe(['dm.inspect', 'directory.read'])),
      'GET /api/directory': page([lea]),
      'GET /api/admin/dm-inspect': page([
        {
          conversation_id: conversation,
          participants: [{ id: lea.id, name: 'Lea Löwe', is_active: true }],
          created_at: '2026-11-13T08:00:00Z',
          last_message_at: null,
        },
      ]),
      'POST /api/admin/dm-inspect': {
        status: 201,
        body: {
          id: 'grant-3',
          conversation_id: conversation,
          reason: 'Prüfung nach Meldung 44',
          granted_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 60 * 60_000).toISOString(),
        },
      },
      'GET /api/admin/dm-inspect/:id/messages': page([
        makeMessage({
          kind: 'system',
          author: null,
          body_md: '',
          system: {
            key: 'run.stopped',
            actor: null,
            number: null,
            old: null,
            new: { value: 'policy_blocked', name: null },
          },
        }),
        makeMessage({
          kind: 'agent',
          body_md: 'Es gibt 30 Tage Urlaub.',
          author: { type: 'agent', id: 'agent-1', name: 'Hilda' },
        }),
      ]),
    })
    const { user } = await renderApp('/admin/dm-inspect')
    await user.click(await screen.findByRole('combobox', { name: 'Person' }))
    await user.click(await screen.findByRole('option', { name: /Lea Löwe/ }))
    await user.click(await screen.findByRole('button', { name: 'Einsicht beantragen' }))
    await user.type(screen.getByLabelText('Begründung'), 'Prüfung nach Meldung 44')
    await user.click(screen.getByRole('button', { name: 'Einsicht beginnen' }))
    const list = await screen.findByRole('list', { name: 'Nachrichten, neueste zuerst' })
    const answer = within(list).getByText('Es gibt 30 Tage Urlaub.').closest('li')!
    expect(within(answer).getByText('Hilda')).toBeInTheDocument()
    expect(within(answer).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(
      within(list).getByText(/Durch die KI-Richtlinie eines Bereichs gestoppt/),
    ).toBeInTheDocument()
    expect(within(list).queryByText('Unbekannt')).toBeNull()
  })

  test('an expired inspection says so instead of showing messages', async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    mockApi({
      ...shellRoutes(makeMe(['dm.inspect', 'directory.read'])),
      'GET /api/directory': page([lea]),
      'GET /api/admin/dm-inspect': page([
        {
          conversation_id: '00000000-0000-7000-a000-000000000002',
          participants: [{ id: lea.id, name: 'Lea Löwe', is_active: true }],
          created_at: '2026-11-13T08:00:00Z',
          last_message_at: null,
        },
      ]),
      'POST /api/admin/dm-inspect': {
        status: 201,
        body: {
          id: 'grant-2',
          conversation_id: '00000000-0000-7000-a000-000000000002',
          reason: 'Prüfung nach Meldung 43',
          granted_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 60 * 60_000).toISOString(),
        },
      },
      'GET /api/admin/dm-inspect/:id/messages': apiError(404, 'dm_inspection.not_found'),
    })
    const { user } = await renderApp('/admin/dm-inspect')
    await user.click(await screen.findByRole('combobox', { name: 'Person' }))
    await user.click(await screen.findByRole('option', { name: /Lea Löwe/ }))
    await user.click(await screen.findByRole('button', { name: 'Einsicht beantragen' }))
    await user.type(screen.getByLabelText('Begründung'), 'Prüfung nach Meldung 43')
    await user.click(screen.getByRole('button', { name: 'Einsicht beginnen' }))
    expect(await screen.findByText(/Die Einsicht ist abgelaufen/)).toBeInTheDocument()
  })
})
