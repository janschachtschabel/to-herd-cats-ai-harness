import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { ADMIN_PERMISSIONS, makeMe, makeUser, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

describe('resetting a person’s two-factor sign-in', () => {
  test('the list marks who has it; the reset asks first and is sent', async () => {
    let withTotp = true
    const lea = () => ({ ...makeUser({ id: 'lea', name: 'Lea Löwe' }), totp_enabled: withTotp })
    const max = { ...makeUser({ id: 'max', name: 'Max Muster' }), totp_enabled: false }
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users/pending/count': { count: 0 },
      'GET /api/admin/users': () => page([lea(), max]),
      'POST /api/admin/users/:id/totp/reset': () => {
        withTotp = false
        return { status: 204 }
      },
    })
    const { user } = await renderApp('/admin/users')
    const leaRow = (await screen.findByRole('cell', { name: /Lea Löwe/ })).closest('tr')!
    expect(within(leaRow).getByLabelText('Zwei-Faktor-Anmeldung eingeschaltet')).toBeInTheDocument()
    const maxRow = screen.getByRole('cell', { name: /Max Muster/ }).closest('tr')!
    expect(within(maxRow).queryByText('2FA')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zwei-Faktor von Max Muster zurücksetzen' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Zwei-Faktor von Lea Löwe zurücksetzen' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('wirklich Lea Löwe fragt')
    await user.click(within(dialog).getByRole('button', { name: 'Zurücksetzen' }))
    await waitFor(() => expect(api.find('POST', '/api/admin/users/lea/totp/reset')).toHaveLength(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(within(leaRow).queryByText('2FA')).not.toBeInTheDocument())
  })
})
