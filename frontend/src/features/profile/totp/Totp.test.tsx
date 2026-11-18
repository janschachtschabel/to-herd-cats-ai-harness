import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import type { TotpStatus } from './queries'

const OFF: TotpStatus = { enabled_at: null, recovery_codes_left: 0, unavailable: null }
const ON: TotpStatus = {
  enabled_at: '2026-11-16T12:00:00Z',
  recovery_codes_left: 10,
  unavailable: null,
}
const CODES = Array.from({ length: 10 }, (_, i) => `AAAAA${i}-BBBBBB-CCCCCC-DDDDDD`)
const SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'

function totpApi(start: TotpStatus) {
  let status = start
  return mockApi({
    'GET /api/auth/me': makeMe(['space.create']),
    'GET /api/spaces': page([]),
    'GET /api/auth/me/identities': page([]),
    'GET /api/auth/providers': page([]),
    'GET /api/auth/me/totp': () => status,
    'GET /api/auth/me/sessions': page([]),
    'POST /api/auth/me/totp/setup': {
      secret: SECRET,
      uri: `otpauth://totp/Org:mia%40example.com?secret=${SECRET}&issuer=Org`,
    },
    'POST /api/auth/me/totp/confirm': () => {
      status = ON
      return { recovery_codes: CODES }
    },
    'POST /api/auth/me/totp/disable': () => {
      status = OFF
      return { status: 204 }
    },
    'POST /api/auth/me/totp/recovery-codes': { recovery_codes: CODES },
  })
}

describe('two-factor sign-in in the profile', () => {
  test('setting it up: password, QR code and key, first code, recovery codes once', async () => {
    const api = totpApi(OFF)
    const { user } = await renderApp('/profile')
    const section = await screen.findByRole('region', { name: 'Zwei-Faktor-Anmeldung' })
    expect(await within(section).findByText('Ausgeschaltet.')).toBeInTheDocument()
    await user.click(within(section).getByRole('button', { name: 'Einrichten' }))

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Aktuelles Passwort'), 'geheim-genug')
    await user.click(within(dialog).getByRole('button', { name: 'Weiter' }))
    expect(api.find('POST', '/api/auth/me/totp/setup')[0]?.body).toEqual({
      password: 'geheim-genug',
    })
    const qr = await within(dialog).findByRole('img', { name: 'QR-Code für die Authenticator-App' })
    expect(qr.tagName.toLowerCase()).toBe('svg')
    expect(within(dialog).getByText('JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP')).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Code aus der App'), '123456')
    await user.click(within(dialog).getByRole('button', { name: 'Einschalten' }))
    expect(api.find('POST', '/api/auth/me/totp/confirm')[0]?.body).toEqual({ code: '123456' })

    const list = await within(dialog).findByRole('list', { name: 'Deine Wiederherstellungscodes' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(10)
    expect(within(dialog).queryByText(/JBSW/)).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Gespeichert, schließen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await within(section).findByText(/Eingeschaltet seit/)).toBeInTheDocument()
    expect(within(section).getByText('Noch 10 Wiederherstellungscodes übrig.')).toBeInTheDocument()
  })

  test('a wrong password stays in the first step with the message', async () => {
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/auth/me/identities': page([]),
      'GET /api/auth/providers': page([]),
      'GET /api/auth/me/totp': OFF,
      'POST /api/auth/me/totp/setup': apiError(422, 'auth.wrong_password'),
    })
    const { user } = await renderApp('/profile')
    await user.click(await screen.findByRole('button', { name: 'Einrichten' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Aktuelles Passwort'), 'falsch')
    await user.click(within(dialog).getByRole('button', { name: 'Weiter' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Das aktuelle Passwort stimmt nicht.',
    )
  })

  test('turning it off with a code', async () => {
    const api = totpApi(ON)
    const { user } = await renderApp('/profile')
    const section = await screen.findByRole('region', { name: 'Zwei-Faktor-Anmeldung' })
    await user.click(await within(section).findByRole('button', { name: 'Ausschalten' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Code oder Wiederherstellungscode'), '654321')
    await user.click(within(dialog).getByRole('button', { name: 'Ausschalten' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/auth/me/totp/disable')[0]?.body).toEqual({ code: '654321' }),
    )
    expect(await within(section).findByText('Ausgeschaltet.')).toBeInTheDocument()
  })

  test('turning it off with a recovery code', async () => {
    const api = totpApi(ON)
    const { user } = await renderApp('/profile')
    await user.click(await screen.findByRole('button', { name: 'Ausschalten' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByLabelText('Code oder Wiederherstellungscode'),
      'aaaaa1-bbbbbb-cccccc-dddddd',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Ausschalten' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/auth/me/totp/disable')[0]?.body).toEqual({
        recovery_code: 'aaaaa1-bbbbbb-cccccc-dddddd',
      }),
    )
  })

  test('new recovery codes need a code and are shown once', async () => {
    const api = totpApi(ON)
    const { user } = await renderApp('/profile')
    await user.click(await screen.findByRole('button', { name: 'Neue Wiederherstellungscodes' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Code aus der App'), '111111')
    await user.click(within(dialog).getByRole('button', { name: 'Neue Codes erzeugen' }))
    const list = await within(dialog).findByRole('list', { name: 'Deine Wiederherstellungscodes' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(10)
    expect(api.find('POST', '/api/auth/me/totp/recovery-codes')[0]?.body).toEqual({
      code: '111111',
    })
  })

  test('an account without a password is told why there is nothing to set up', async () => {
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/auth/me/identities': page([]),
      'GET /api/auth/providers': page([]),
      'GET /api/auth/me/totp': { ...OFF, unavailable: 'no_password' },
    })
    await renderApp('/profile')
    expect(await screen.findByText(/meldet sich über einen Anbieter an/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Einrichten' })).not.toBeInTheDocument()
  })
})
