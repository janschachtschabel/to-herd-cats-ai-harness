import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission, Space, WikiPage } from '@/lib/api'
import { makeAttachment, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

function spaceApi(permissions: Permission[], space: Space) {
  return mockApi({
    'GET /api/auth/me': makeMe(permissions),
    'GET /api/spaces': page([space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/members': page([]),
    'PATCH /api/spaces/:id': (call) => ({ ...space, ...(call.body as object), version: 2 }),
  })
}

async function openSettings(space: Space) {
  const app = await renderApp(`/spaces/${space.id}/settings`)
  await app.user.click(await screen.findByRole('button', { name: 'Einstellungen' }))
  return { ...app, dialog: await screen.findByRole('dialog') }
}

describe('ai settings of content', () => {
  test('a space admin with AI restricts the space to chosen locations', async () => {
    const space = makeSpace({ my_role: 'admin' })
    const api = spaceApi(['ai.use'], space)
    const { user, dialog } = await openSettings(space)
    const policy = within(dialog).getByRole('group', { name: 'KI-Richtlinie' })
    expect(within(policy).getByLabelText(/Jede Verbindung/)).toBeChecked()
    await user.click(within(policy).getByLabelText(/Nur bestimmte Datenorte/))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(
      await within(dialog).findByText('Bitte mindestens einen Datenort wählen.'),
    ).toBeInTheDocument()
    expect(api.find('PATCH', `/api/spaces/${space.id}`)).toEqual([])

    await user.click(within(policy).getByLabelText('EU'))
    await user.click(within(policy).getByLabelText('Lokal'))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PATCH', `/api/spaces/${space.id}`)).toHaveLength(1))
    expect(api.find('PATCH', `/api/spaces/${space.id}`)[0]?.body).toMatchObject({
      ai_policy: 'restricted',
      allowed_locations: ['local', 'eu'],
      version: 1,
    })
  })

  test('a space admin without AI still sets the policy (governance, not use)', async () => {
    const space = makeSpace({ my_role: 'admin' })
    const api = spaceApi([], space)
    const { user, dialog } = await openSettings(space)
    const policy = within(dialog).getByRole('group', { name: 'KI-Richtlinie' })
    await user.click(within(policy).getByLabelText(/Keine KI/))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PATCH', `/api/spaces/${space.id}`)).toHaveLength(1))
    expect(api.find('PATCH', `/api/spaces/${space.id}`)[0]?.body).toMatchObject({
      ai_policy: 'none',
      version: 1,
    })
  })

  function wikiApi(permissions: Permission[], role: Space['my_role'], current: WikiPage) {
    const space = makeSpace({ id: current.space_id, my_role: role })
    const file = makeAttachment({ page_id: current.id, filename: 'plan.pdf' })
    let shown = current
    const api = mockApi({
      'GET /api/auth/me': makeMe(permissions),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/pages/tree': page([nodeOf(current)]),
      'GET /api/spaces/:id/pages/by-path': () => shown,
      'GET /api/tags': page([]),
      'GET /api/pages/:id/attachments': page([file]),
      'GET /api/pages/:id/tickets': page([]),
      'PUT /api/pages/:id/ai-lock': (call) => {
        shown = { ...shown, no_ai: (call.body as { no_ai: boolean }).no_ai, version: 2 }
        return shown
      },
      'PUT /api/attachments/:id/ai-lock': (call) => ({ ...file, ...(call.body as object) }),
    })
    return { api, space, file }
  }

  test('a moderator with AI locks a page and a file for AI', async () => {
    const current = makePage({ space_id: '00000000-0000-7000-8000-0000000000aa' })
    const { api, space, file } = wikiApi(['ai.use'], 'moderator', current)
    const { user } = await renderApp(`/spaces/${space.id}/p/${current.path}`)
    await screen.findByRole('heading', { level: 2, name: current.title })
    expect(screen.queryByText('Für KI gesperrt')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Weitere Aktionen' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Für KI sperren' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/pages/${current.id}/ai-lock`)[0]?.body).toEqual({
        no_ai: true,
        version: 1,
      }),
    )
    expect(await screen.findByText('Für KI gesperrt')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'plan.pdf für KI sperren' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/attachments/${file.id}/ai-lock`)[0]?.body).toEqual({
        no_ai: true,
        version: 1,
      }),
    )
  })

  test('a moderator without AI sees and sets the lock (governance, not use)', async () => {
    const current = makePage({ space_id: '00000000-0000-7000-8000-0000000000ab', no_ai: true })
    const { api, space } = wikiApi([], 'moderator', current)
    const { user } = await renderApp(`/spaces/${space.id}/p/${current.path}`)
    await screen.findByRole('heading', { level: 2, name: current.title })
    expect(screen.getByText('Für KI gesperrt')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Weitere Aktionen' }))
    await user.click(await screen.findByRole('menuitem', { name: 'KI-Sperre aufheben' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/pages/${current.id}/ai-lock`)[0]?.body).toEqual({
        no_ai: false,
        version: 1,
      }),
    )
  })

  test('a reader without AI sees nothing about AI, not even on a locked page', async () => {
    const current = makePage({ space_id: '00000000-0000-7000-8000-0000000000ac', no_ai: true })
    const { space } = wikiApi([], 'viewer', current)
    await renderApp(`/spaces/${space.id}/p/${current.path}`)
    await screen.findByRole('heading', { level: 2, name: current.title })
    expect(screen.queryByText('Für KI gesperrt')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /für KI sperren/ })).not.toBeInTheDocument()
  })

  test('the profile shows my model and usage only with AI', async () => {
    const usage = {
      calls: 4,
      tokens_in: 2000,
      tokens_out: 500,
      tokens_cached: 0,
      cost: '0.0125',
      unpriced_calls: 0,
      duration_ms: 1200,
      first_day: '2026-10-16',
      last_day: '2026-11-14',
    }
    const me = { ...makeMe(['ai.use']), ai_model: 'gpt-6-luna' }
    mockApi({ 'GET /api/auth/me': me, 'GET /api/spaces': page([]), 'GET /api/ai/usage/me': usage })
    await renderApp('/profile')
    const section = await screen.findByRole('region', { name: 'Meine KI' })
    expect(within(section).getByText('Dein Modell: gpt-6-luna')).toBeInTheDocument()
    expect(await within(section).findByText('2.000')).toBeInTheDocument()
    expect(within(section).getByText('0,0125')).toBeInTheDocument()
  })

  test('without AI the profile has no AI section and asks nothing', async () => {
    const api = mockApi({ 'GET /api/auth/me': makeMe([]), 'GET /api/spaces': page([]) })
    await renderApp('/profile')
    expect(await screen.findByRole('heading', { name: 'Profil' })).toBeInTheDocument()
    expect(screen.queryByText('Meine KI')).not.toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/ai'))).toEqual([])
  })
})
