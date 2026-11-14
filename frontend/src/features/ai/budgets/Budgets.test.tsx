import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission, Schemas } from '@/lib/api'
import { apiError, makeEntry, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

type Budget = Schemas['BudgetOut']

const ADMIN: Permission[] = ['ai.manage', 'directory.read', 'user.manage']
const AGENT_ID = '00000000-0000-7000-8000-0000000000a1'
const LEA_ID = '00000000-0000-7000-8000-0000000000b1'

function makeBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    id: '00000000-0000-7000-8000-00000000d001',
    scope: 'organisation',
    subject_id: null,
    name: null,
    tokens_per_day: 50_000,
    cost_per_day: '5.00',
    version: 1,
    today: {
      tokens: 12_345,
      cost: '0.12',
      unpriced_calls: 0,
      tokens_reached: false,
      cost_reached: false,
      exhausted: false,
    },
    ...overrides,
  }
}

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
})

describe('budgets in the AI administration', () => {
  test('without ai.manage: not found, no budget request', async () => {
    const api = mockApi(shell(['user.manage', 'ai.use']))
    await renderApp('/admin/ai/budgets')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/ai'))).toEqual([])
  })

  test("lists each budget with today's use, says what a currency limit counts", async () => {
    mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': page([
        makeBudget(),
        makeBudget({
          id: '00000000-0000-7000-8000-00000000d002',
          scope: 'agent',
          subject_id: AGENT_ID,
          name: 'Hilda',
          tokens_per_day: null,
          cost_per_day: '1.50',
          today: {
            tokens: 900,
            cost: '1.50',
            unpriced_calls: 3,
            tokens_reached: false,
            cost_reached: true,
            exhausted: true,
          },
        }),
      ]),
    })
    const { user } = await renderApp('/admin/ai')
    await user.click(await screen.findByRole('link', { name: 'Budgets' }))
    expect(
      await screen.findByText(/Ein Währungslimit zählt nur Aufrufe mit hinterlegtem Preis/),
    ).toBeInTheDocument()
    const list = await screen.findByRole('list', { name: 'Budgets' })
    const [org, agent] = within(list).getAllByRole('listitem')
    expect(within(org!).getByText('Organisation')).toBeInTheDocument()
    expect(within(org!).getByText('12.345 von 50.000 Tokens')).toBeInTheDocument()
    expect(within(org!).getByText(/^0,12\s€ von 5,00\s€$/)).toBeInTheDocument()
    expect(within(org!).queryByText('Limit erreicht')).toBeNull()
    expect(within(agent!).getByText('Agent: Hilda')).toBeInTheDocument()
    expect(within(agent!).getByText('900 Tokens (kein Token-Limit)')).toBeInTheDocument()
    expect(within(agent!).getByText('Limit erreicht')).toBeInTheDocument()
    expect(
      within(agent!).getByText('3 Aufrufe ohne Preis (zählen nur für Tokens)'),
    ).toBeInTheDocument()
  })

  test('no budget yet says so; a failed list can be retried', async () => {
    let fail = true
    mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': () => (fail ? apiError(500, 'internal') : page([])),
    })
    const { user } = await renderApp('/admin/ai/budgets')
    fail = false
    await user.click(await screen.findByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByText(/Noch kein Budget gesetzt/)).toBeInTheDocument()
  })

  test('sets the organisation a token limit; a form without any limit is refused', async () => {
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': page([]),
      'PUT /api/ai/budgets/organisation': (call) =>
        makeBudget({ ...(call.body as object), cost_per_day: null }),
    })
    const { user } = await renderApp('/admin/ai/budgets')
    const form = await screen.findByRole('form', { name: 'Budget setzen' })
    await user.click(within(form).getByRole('button', { name: 'Budget setzen' }))
    expect(
      await within(form).findByText('Bitte ein Token- oder ein Währungslimit angeben.'),
    ).toBeInTheDocument()
    expect(api.find('PUT', '/api/ai/budgets/organisation')).toEqual([])

    await user.type(within(form).getByLabelText('Euro je Tag'), '1.000')
    await user.click(within(form).getByRole('button', { name: 'Budget setzen' }))
    expect(
      await within(form).findByText('Ein Betrag in Euro, zum Beispiel 5 oder 2,50.'),
    ).toBeInTheDocument()
    await user.clear(within(form).getByLabelText('Euro je Tag'))
    await user.type(within(form).getByLabelText('Tokens je Tag'), '50000')
    await user.click(within(form).getByRole('button', { name: 'Budget setzen' }))
    await waitFor(() => expect(api.find('PUT', '/api/ai/budgets/organisation')).toHaveLength(1))
    expect(api.find('PUT', '/api/ai/budgets/organisation')[0]!.body).toEqual({
      tokens_per_day: 50000,
      cost_per_day: null,
      version: null,
    })
  })

  test('sets a person a currency limit (comma as the decimal mark)', async () => {
    const lea = makeEntry({ id: LEA_ID, name: 'Lea Löwe' })
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': page([]),
      'GET /api/directory': page([lea]),
      'PUT /api/ai/budgets/users/:id': (call) => makeBudget(call.body as object),
    })
    const { user } = await renderApp('/admin/ai/budgets')
    const form = await screen.findByRole('form', { name: 'Budget setzen' })
    await user.selectOptions(within(form).getByLabelText('Gilt für'), 'Eine Person')
    await user.type(within(form).getByRole('combobox', { name: 'Person' }), 'Lea')
    await user.click(await screen.findByRole('option', { name: /Lea Löwe/ }))
    await user.type(within(form).getByLabelText('Euro je Tag'), '2,50')
    await user.click(within(form).getByRole('button', { name: 'Budget setzen' }))
    await waitFor(() => expect(api.find('PUT', `/api/ai/budgets/users/${LEA_ID}`)).toHaveLength(1))
    expect(api.find('PUT', `/api/ai/budgets/users/${LEA_ID}`)[0]!.body).toEqual({
      tokens_per_day: null,
      cost_per_day: '2.50',
      version: null,
    })
  })

  test('agents are offered to those who manage them', async () => {
    const api = mockApi({
      ...shell([...ADMIN, 'agent.manage']),
      'GET /api/ai/budgets': page([]),
      'GET /api/agents': page([{ id: AGENT_ID, name: 'Hilda', status: 'active' }]),
      'PUT /api/ai/budgets/agents/:id': (call) => makeBudget(call.body as object),
    })
    const { user } = await renderApp('/admin/ai/budgets')
    const form = await screen.findByRole('form', { name: 'Budget setzen' })
    await user.selectOptions(within(form).getByLabelText('Gilt für'), 'Ein Agent')
    await user.selectOptions(await within(form).findByLabelText('Agent'), 'Hilda')
    await user.type(within(form).getByLabelText('Tokens je Tag'), '1000')
    await user.click(within(form).getByRole('button', { name: 'Budget setzen' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/ai/budgets/agents/${AGENT_ID}`)).toHaveLength(1),
    )
  })

  test('without agent.manage the agent scope says why it cannot be picked', async () => {
    const api = mockApi({ ...shell(ADMIN), 'GET /api/ai/budgets': page([]) })
    const { user } = await renderApp('/admin/ai/budgets')
    const form = await screen.findByRole('form', { name: 'Budget setzen' })
    await user.selectOptions(within(form).getByLabelText('Gilt für'), 'Ein Agent')
    expect(within(form).getByText(/Agenten wählen kann, wer Agenten verwaltet/)).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Budget setzen' })).toBeDisabled()
    expect(api.find('GET', '/api/agents')).toEqual([])
  })

  test('a changed limit names a newer version; after reloading it saves', async () => {
    let budget = makeBudget()
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': () => page([budget]),
      'PUT /api/ai/budgets/organisation': (call) => {
        const body = call.body as Schemas['BudgetIn']
        if (body.version !== budget.version) {
          return apiError(409, 'ai.budget_version_conflict', 'stale', { current_version: 2 })
        }
        return makeBudget({ ...budget, tokens_per_day: body.tokens_per_day ?? null })
      },
    })
    const { user } = await renderApp('/admin/ai/budgets')
    budget = makeBudget({ version: 2 })
    await user.click(await screen.findByRole('button', { name: 'Budget Organisation ändern' }))
    const dialog = await screen.findByRole('dialog')
    const tokens = within(dialog).getByLabelText('Tokens je Tag')
    expect(tokens).toHaveValue(50000)
    await user.clear(tokens)
    await user.type(tokens, '80000')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(
      await within(dialog).findByText(/Jemand hat diesen Eintrag inzwischen geändert/),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await waitFor(() => expect(api.find('GET', '/api/ai/budgets').length).toBeGreaterThan(1))
    expect(tokens).toHaveValue(80000)
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PUT', '/api/ai/budgets/organisation').at(-1)!.body).toEqual({
      tokens_per_day: 80000,
      cost_per_day: '5.00',
      version: 2,
    })
  })

  test('removes a budget after asking, with its version', async () => {
    const budget = makeBudget({ scope: 'user', subject_id: LEA_ID, name: 'Lea Löwe', version: 4 })
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/ai/budgets': page([budget]),
      'DELETE /api/ai/budgets/:id': { status: 204 },
    })
    const { user } = await renderApp('/admin/ai/budgets')
    await user.click(
      await screen.findByRole('button', { name: 'Budget Person: Lea Löwe entfernen' }),
    )
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Entfernen' }))
    await waitFor(() => expect(api.find('DELETE', `/api/ai/budgets/${budget.id}`)).toHaveLength(1))
    expect(api.find('DELETE', `/api/ai/budgets/${budget.id}`)[0]!.query.get('version')).toBe('4')
  })
})
