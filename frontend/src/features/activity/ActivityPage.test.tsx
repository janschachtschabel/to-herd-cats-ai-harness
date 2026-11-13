import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { makeActivity, makeConversation, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

describe('activity', () => {
  test('entries lead into their conversation; done and read-all are sent', async () => {
    const channel = makeConversation({ id: 'c-1' })
    const entry = makeActivity()
    const api = mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'POST /api/activity/:id/read': { status: 204 },
      'POST /api/activity/:id/done': { status: 204 },
      'POST /api/activity/read-all': { status: 204 },
      'GET /api/conversations/:id': channel,
      'GET /api/conversations/:id/messages': page([]),
      'GET /api/spaces/:id': { status: 404, body: { error: { code: 'space.not_found' } } },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText('Lea Löwe')).closest('li')!
    expect(item).toHaveTextContent('hat dich in # allgemein erwähnt')
    expect(item).toHaveTextContent('Hallo @Mia Muster')
    await user.click(
      within(item).getByRole('button', { name: 'Eintrag von Lea Löwe als erledigt markieren' }),
    )
    await user.click(screen.getByRole('button', { name: 'Alle als gelesen markieren' }))
    await waitFor(() => expect(api.find('POST', '/api/activity/read-all')).toHaveLength(1))
    expect(api.find('POST', `/api/activity/${entry.id}/done`)).toHaveLength(1)

    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/c/c-1'))
    expect(router.state.location.search).toEqual({ message: entry.message_id })
    expect(api.find('POST', `/api/activity/${entry.id}/read`)).toHaveLength(1)
  })

  test('nothing for me says so', async () => {
    mockApi({ ...shellRoutes(makeMe([])), 'GET /api/activity': page([]) })
    await renderApp('/activity')
    expect(await screen.findByText('Nichts Neues für dich.')).toBeInTheDocument()
  })
})
