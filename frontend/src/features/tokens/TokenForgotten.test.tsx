// Module review M8 2, finding G3: the clear text of a new access token is shown
// once, but the finished mutation keeps the API's answer (`state.data`) in
// TanStack's mutation cache for five minutes after the dialog is closed. A correct
// client forgets it when the person closes the dialog (as the AI key and the
// connectors' secrets are forgotten: `gcTime: 0`, `FORGET_VARIABLES`).
import { screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { created, makeToken } from '@/test/tokens'

const SECRET = 'herd_pat_wegwerf-nur-im-test-0000000000000000000'

test('once the dialog is closed, the token is nowhere in the client’s memory', async () => {
  mockApi({
    'GET /api/auth/me': makeMe(['mcp.use']),
    'GET /api/spaces': page([makeSpace({ name: 'Betrieb' })]),
    'GET /api/tokens': page([]),
    'POST /api/tokens': { status: 201, body: created(makeToken({ name: 'Codex' }), SECRET) },
  })
  const { user, queryClient } = await renderApp('/profile/tokens')
  await user.click(await screen.findByRole('button', { name: 'Token anlegen' }))
  const dialog = await screen.findByRole('dialog', { name: 'Zugangstoken anlegen' })
  await user.type(within(dialog).getByLabelText('Name'), 'Codex')
  await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
  const shown = await screen.findByRole('dialog', { name: 'Dein neues Token: Codex' })
  await user.click(within(shown).getByRole('button', { name: 'Fertig' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  const kept = queryClient
    .getMutationCache()
    .getAll()
    .map((m) => [m.state.data, m.state.variables])
  expect(JSON.stringify(kept)).not.toContain(SECRET)
})
