import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Space } from '@/lib/api'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

function settingsApi(initial: Space) {
  let current = initial
  const api = mockApi({
    'GET /api/auth/me': makeMe([]),
    'GET /api/spaces': () => page([current]),
    'GET /api/spaces/:id': () => current,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/members': page([]),
    'PATCH /api/spaces/:id': (call) => {
      current = { ...current, ...(call.body as Partial<Space>), version: current.version + 1 }
      return current
    },
  })
  return api
}

async function openSettings(space: Space) {
  const { user } = await renderApp(`/spaces/${space.id}/settings`)
  await user.click(await screen.findByRole('button', { name: 'Einstellungen' }))
  const dialog = await screen.findByRole('dialog')
  return { user, dialog }
}

describe("a space's review interval", () => {
  test('those who manage the space switch it on with a number of days', async () => {
    const space = makeSpace({ version: 2 })
    const api = settingsApi(space)
    const { user, dialog } = await openSettings(space)
    const group = within(dialog).getByRole('group', { name: 'Prüffrist für Seiten' })
    const toggle = within(group).getByRole('checkbox', { name: 'Seiten regelmäßig prüfen' })
    expect(toggle).not.toBeChecked()
    expect(within(group).queryByLabelText('Prüfen alle … Tage')).toBeNull()
    await user.click(toggle)
    const days = within(group).getByLabelText('Prüfen alle … Tage')
    await user.clear(days)
    await user.type(days, '5')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(
      await within(group).findByText('Eine ganze Zahl von 7 bis 730 Tagen.'),
    ).toBeInTheDocument()
    expect(api.find('PATCH', `/api/spaces/${space.id}`)).toEqual([])

    await user.clear(days)
    await user.type(days, '30')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PATCH', `/api/spaces/${space.id}`)[0]!.body).toMatchObject({
      review_interval_days: 30,
      version: 2,
    })
  })

  test('switching it off sends null', async () => {
    const space = makeSpace({ review_interval_days: 90 })
    const api = settingsApi(space)
    const { user, dialog } = await openSettings(space)
    expect(within(dialog).getByLabelText('Prüfen alle … Tage')).toHaveValue(90)
    await user.click(within(dialog).getByRole('checkbox', { name: 'Seiten regelmäßig prüfen' }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PATCH', `/api/spaces/${space.id}`)).toHaveLength(1))
    expect(api.find('PATCH', `/api/spaces/${space.id}`)[0]!.body).toMatchObject({
      review_interval_days: null,
    })
  })

  test('members who do not manage the space get no settings', async () => {
    const space = makeSpace({ my_role: 'moderator', review_interval_days: 30 })
    settingsApi(space)
    await renderApp(`/spaces/${space.id}/settings`)
    await screen.findByRole('heading', { name: 'Mitglieder' })
    expect(screen.queryByRole('button', { name: 'Einstellungen' })).toBeNull()
  })
})
