import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { created, makeToken } from '@/test/tokens'

const SECRET = 'herd_pat_wegwerf-nur-im-test-0000000000000000000'

describe('a new token for a person with two-factor sign-in', () => {
  test('asks for a current code and sends it along', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(['mcp.use']),
      'GET /api/spaces': page([]),
      'GET /api/tokens': page([]),
      'GET /api/auth/me/totp': {
        enabled_at: '2026-11-16T12:00:00Z',
        recovery_codes_left: 10,
        unavailable: null,
      },
      'POST /api/tokens': { status: 201, body: created(makeToken({ name: 'Codex' }), SECRET) },
    })
    const { user } = await renderApp('/profile/tokens')
    await user.click(await screen.findByRole('button', { name: 'Token anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Zugangstoken anlegen' })
    await user.type(within(dialog).getByLabelText('Name'), 'Codex')
    await user.type(
      await within(dialog).findByLabelText('Code aus der Authenticator-App'),
      '123456',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/tokens')).toHaveLength(1))
    expect(api.find('POST', '/api/tokens')[0]!.body).toMatchObject({
      name: 'Codex',
      second_factor_code: '123456',
    })
  })

  test('without it there is no code field', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(['mcp.use']),
      'GET /api/spaces': page([]),
      'GET /api/tokens': page([]),
      'GET /api/auth/me/totp': { enabled_at: null, recovery_codes_left: 0, unavailable: null },
    })
    const { user } = await renderApp('/profile/tokens')
    await user.click(await screen.findByRole('button', { name: 'Token anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Zugangstoken anlegen' })
    expect(within(dialog).getByLabelText('Name')).toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Code aus der Authenticator-App')).toBeNull()
  })
})
