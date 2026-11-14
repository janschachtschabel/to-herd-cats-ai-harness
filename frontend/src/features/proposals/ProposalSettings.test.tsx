import { screen, waitFor, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, test } from 'vitest'
import { systemText } from '@/features/messaging/display'
import { makeMe, makePage, makeSpace, makeVersion, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

describe('around proposals', () => {
  test('a space admin sets how agents change pages', async () => {
    const space = makeSpace({ my_role: 'admin', version: 2 })
    const api = mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/pages/tree': page([]),
      'GET /api/spaces/:id/members': page([]),
      'GET /api/spaces/:id/proposals': page([]),
      'PATCH /api/spaces/:id': { ...space, agent_write_policy: 'direct', version: 3 },
    })
    const { user } = await renderApp(`/spaces/${space.id}/settings`)
    await user.click(await screen.findByRole('button', { name: 'Einstellungen' }))
    const dialog = await screen.findByRole('dialog')
    const policy = within(dialog).getByRole('group', { name: 'Wie Agenten Seiten ändern' })
    expect(within(policy).getByRole('radio', { name: /Vorschlagen/ })).toBeChecked()
    await user.click(within(policy).getByRole('radio', { name: /Direkt schreiben/ }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/spaces/${space.id}`)[0]?.body).toMatchObject({
        agent_write_policy: 'direct',
        version: 2,
      }),
    )
  })

  test('versions written for an agent carry the AI mark', async () => {
    const space = makeSpace({ my_role: 'editor' })
    const doc = makePage({ space_id: space.id, path: 'handbuch' })
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/pages/tree': page([nodeOf(doc)]),
      'GET /api/spaces/:id/pages/by-path': doc,
      'GET /api/spaces/:id/proposals': page([]),
      'GET /api/pages/:id/versions': page([
        makeVersion(2, {
          source: 'agent',
          ai: true,
          author: { type: 'agent', id: 'a', name: 'Hilda' },
        }),
        makeVersion(1),
      ]),
      'GET /api/pages/:id/diff': {
        from_number: 1,
        to_number: 2,
        from_title: 'Handbuch',
        to_title: 'Handbuch',
        title_changed: false,
        hunks: [],
      },
    })
    await renderApp(`/spaces/${space.id}/p/handbuch?view=versions`)
    const rows = await screen.findAllByRole('row')
    const agentRow = rows.find((r) => within(r).queryByText('Hilda'))!
    expect(within(agentRow).getByText('Von einem Agenten')).toBeInTheDocument()
    expect(within(agentRow).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    const humanRow = rows.find((r) => within(r).queryByText('Lea Löwe'))!
    expect(within(humanRow).queryByText('Von einer KI geschrieben')).toBeNull()
  })

  test('the page thread tells of proposals in words', () => {
    const t = i18n.t.bind(i18n)
    const entry = (key: string) => ({ key, actor: { id: 'a', name: 'Hilda' }, number: null })
    expect(systemText(t, entry('proposal.created') as never)).toBe(
      'Hilda hat einen Vorschlag eingereicht.',
    )
    expect(systemText(t, entry('proposal.accepted') as never)).toBe(
      'Hilda hat einen Vorschlag angenommen.',
    )
    expect(systemText(t, entry('proposal.rejected') as never)).toBe(
      'Hilda hat einen Vorschlag abgelehnt.',
    )
    expect(systemText(t, entry('proposal.withdrawn') as never)).toBe(
      'Hilda hat einen Vorschlag zurückgezogen.',
    )
  })
})
