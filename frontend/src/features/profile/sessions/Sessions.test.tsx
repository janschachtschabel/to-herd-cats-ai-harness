import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import type { OwnSession } from './queries'

const TOTP_OFF = { enabled_at: null, recovery_codes_left: 0, unavailable: null }
const HERE: OwnSession = {
  id: '0193a1b2-0000-7000-8000-000000000001',
  device: 'Firefox · Linux',
  signed_in_at: '2026-11-18T08:00:00Z',
  last_used_at: '2026-11-18T09:30:00Z',
  current: true,
}
const PHONE: OwnSession = {
  id: '0193a1b2-0000-7000-8000-000000000002',
  device: 'Safari · iOS',
  signed_in_at: '2026-11-17T18:00:00Z',
  last_used_at: '2026-11-17T21:10:00Z',
  current: false,
}
const UNKNOWN: OwnSession = { ...PHONE, id: '0193a1b2-0000-7000-8000-000000000003', device: null }

function sessionsApi(start: OwnSession[]) {
  let sessions = start
  return mockApi({
    'GET /api/auth/me': makeMe(['space.create']),
    'GET /api/spaces': page([]),
    'GET /api/auth/me/totp': TOTP_OFF,
    'GET /api/auth/me/identities': page([]),
    'GET /api/auth/providers': page([]),
    'GET /api/auth/me/sessions': () => page(sessions),
    'DELETE /api/auth/me/sessions/:id': (_call, params) => {
      sessions = sessions.filter((s) => s.id !== params.id)
      return { status: 204 }
    },
    'POST /api/auth/me/sessions/sign-out-others': () => {
      sessions = sessions.filter((s) => s.current)
      return { status: 204 }
    },
  })
}

describe('own sessions in the profile', () => {
  test('lists the sessions with device and times, this one marked, and ends another', async () => {
    const api = sessionsApi([HERE, PHONE, UNKNOWN])
    const { user } = await renderApp('/profile')
    const section = await screen.findByRole('region', { name: 'Angemeldete Geräte' })
    const items = await within(section).findAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(within(items[0]!).getByText('Firefox · Linux')).toBeInTheDocument()
    expect(within(items[0]!).getByText('Dieses Gerät')).toBeInTheDocument()
    expect(within(items[0]!).queryByRole('button')).not.toBeInTheDocument()
    expect(within(items[1]!).getByText(/Angemeldet am/)).toBeInTheDocument()
    expect(within(items[1]!).getByText(/Zuletzt genutzt/)).toBeInTheDocument()
    expect(within(items[2]!).getByText('Unbekanntes Gerät')).toBeInTheDocument()

    await user.click(within(items[1]!).getByRole('button', { name: 'Safari · iOS abmelden' }))
    expect(api.find('DELETE', `/api/auth/me/sessions/${PHONE.id}`)).toHaveLength(1)
    await waitFor(() => expect(within(section).getAllByRole('listitem')).toHaveLength(2))
  })

  test('signs out every other session after asking', async () => {
    const api = sessionsApi([HERE, PHONE])
    const { user } = await renderApp('/profile')
    const section = await screen.findByRole('region', { name: 'Angemeldete Geräte' })
    await within(section).findAllByRole('listitem')
    await user.click(within(section).getByRole('button', { name: 'Alle anderen abmelden' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Alle anderen abmelden' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/auth/me/sessions/sign-out-others')).toHaveLength(1),
    )
    await waitFor(() => expect(within(section).getAllByRole('listitem')).toHaveLength(1))
    expect(within(section).queryByRole('button', { name: 'Alle anderen abmelden' })).toBeNull()
  })
})
