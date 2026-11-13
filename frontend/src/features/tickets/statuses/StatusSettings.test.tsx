import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole, TicketStatus } from '@/lib/api'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { STATUSES } from '@/test/tickets'

function settingsApi(role: SpaceRole, extra = {}) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  let statuses: TicketStatus[] = STATUSES
  const api = mockApi({
    ...shellRoutes(makeMe(['directory.read']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/members': page([]),
    'GET /api/tags': page([]),
    'GET /api/spaces/:id/ticket-statuses': () => page(statuses),
    ...extra,
  })
  return { api, set: (next: TicketStatus[]) => void (statuses = next) }
}

const section = () => screen.findByRole('region', { name: 'Ticket-Status' })

describe('status settings', () => {
  test('only a space admin sees the workflow', async () => {
    settingsApi('moderator')
    await renderApp('/spaces/space-1/settings')
    expect(await screen.findByRole('heading', { name: 'Mitglieder' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Ticket-Status' })).toBeNull()
  })

  test('an admin adds, renames, re-categorises and moves statuses', async () => {
    const { api, set } = settingsApi('admin', {
      'POST /api/spaces/:id/ticket-statuses': {
        status: 201,
        body: { ...STATUSES[1]!, id: 'new', name: 'Wartet', position: 5 },
      },
      'PATCH /api/ticket-statuses/:id': (call: { body: unknown }) => ({
        ...STATUSES[1]!,
        ...(call.body as object),
        version: 2,
      }),
    })
    const { user } = await renderApp('/spaces/space-1/settings')
    const statuses = await section()
    const rows = await within(statuses).findAllByRole('listitem')
    expect(rows).toHaveLength(5)
    expect(within(statuses).getByRole('button', { name: 'Neu nach oben' })).toBeDisabled()
    expect(within(statuses).getByRole('button', { name: 'Verworfen nach unten' })).toBeDisabled()

    const form = within(statuses).getByRole('form', { name: 'Status hinzufügen' })
    await user.type(within(form).getByRole('textbox', { name: 'Name' }), 'Wartet')
    await user.selectOptions(within(form).getByRole('combobox', { name: 'Kategorie' }), 'review')
    await user.click(within(form).getByRole('button', { name: 'Hinzufügen' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/spaces/space-1/ticket-statuses')[0]!.body).toEqual({
        name: 'Wartet',
        category: 'review',
      }),
    )

    const name = within(statuses).getByRole('textbox', { name: 'Name von In Arbeit' })
    await user.clear(name)
    await user.type(name, 'Läuft')
    set(STATUSES.map((s) => (s.id === STATUSES[1]!.id ? { ...s, name: 'Läuft', version: 2 } : s)))
    await user.click(within(statuses).getByRole('button', { name: 'Speichern' }))
    const patches = () => api.find('PATCH', `/api/ticket-statuses/${STATUSES[1]!.id}`)
    await waitFor(() => expect(patches()[0]!.body).toEqual({ name: 'Läuft', version: 1 }))
    // The workflow is read again: later changes go out with the new version.
    await user.click(await within(statuses).findByRole('button', { name: 'Läuft nach oben' }))
    await waitFor(() => expect(patches()[1]!.body).toEqual({ position: 0, version: 2 }))
    await user.selectOptions(
      within(statuses).getByRole('combobox', { name: 'Kategorie von Läuft' }),
      'review',
    )
    await waitFor(() => expect(patches()[2]!.body).toEqual({ category: 'review', version: 2 }))
  })

  test('deleting a status names where its tickets go', async () => {
    const { api } = settingsApi('admin', {
      'DELETE /api/ticket-statuses/:id': { status: 204 },
    })
    const { user } = await renderApp('/spaces/space-1/settings')
    const statuses = await section()
    await user.click(await within(statuses).findByRole('button', { name: 'Zur Prüfung löschen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Status „Zur Prüfung“ löschen' })
    const target = within(dialog).getByRole('combobox', { name: 'Tickets wechseln nach' })
    expect(within(target).queryByRole('option', { name: 'Zur Prüfung' })).toBeNull()
    await user.selectOptions(target, 'In Arbeit')
    await user.click(within(dialog).getByRole('button', { name: 'Löschen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const sent = api.find('DELETE', `/api/ticket-statuses/${STATUSES[2]!.id}`)[0]!
    expect(sent.query.get('replace_with')).toBe(STATUSES[1]!.id)
    expect(sent.query.get('version')).toBe('1')
  })
})
