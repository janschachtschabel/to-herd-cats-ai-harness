import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole } from '@/lib/api'
import { apiError, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { makeProposal, makeProposalDetail } from '@/test/proposals'
import { renderApp } from '@/test/render'

const space = makeSpace({ name: 'Handbuch', my_role: 'moderator' })
const urlaub = makePage({ id: 'page-1', space_id: space.id, title: 'Urlaub', path: 'urlaub' })

function proposalApi(role: SpaceRole, extra: Record<string, unknown> = {}) {
  const roleSpace = { ...space, my_role: role }
  return mockApi({
    'GET /api/auth/me': makeMe(['ai.use']),
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    'GET /api/spaces/:id/pages/tree': page([nodeOf(urlaub)]),
    'GET /api/spaces/:id/pages/by-path': urlaub,
    'GET /api/pages/:id/attachments': page([]),
    'GET /api/pages/:id/tickets': page([]),
    ...extra,
  })
}

describe('proposals', () => {
  test('the tab counts the open ones; the list names page, AI author and reason', async () => {
    const one = makeProposal({ space_id: space.id })
    const two = makeProposal({
      space_id: space.id,
      kind: 'new',
      page_id: null,
      parent_id: urlaub.id,
      title: 'Elternzeit',
      author: { type: 'user', id: 'u1', name: 'Lea Löwe' },
      ai: false,
    })
    proposalApi('moderator', { 'GET /api/spaces/:id/proposals': page([one, two]) })
    const { user } = await renderApp(`/spaces/${space.id}`)
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    const tab = await within(tabs).findByRole('link', { name: /Vorschläge/ })
    expect(within(tab).getByText('2')).toBeInTheDocument()
    await user.click(tab)
    // The view moves from the wiki's column to the full width once the route settles.
    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'Änderung an „Urlaub“' })
      const first = link.closest('li')!
      expect(within(first).getByText('Von einer KI geschrieben')).toBeInTheDocument()
      expect(within(first).getByText('Die Frist ist jetzt 30 Tage.')).toBeInTheDocument()
      const second = screen.getByRole('link', { name: 'Neue Seite „Elternzeit“ unter „Urlaub“' })
      expect(within(second.closest('li')!).queryByText('Von einer KI geschrieben')).toBeNull()
    })
  })

  test('a moderator reads the diff and accepts', async () => {
    const detail = makeProposalDetail({ space_id: space.id })
    const api = proposalApi('moderator', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
      'POST /api/proposals/:id/accept': { ...detail, state: 'accepted', version: 2 },
    })
    const { user } = await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    const diff = await screen.findByRole('region', { name: 'Änderungen des Vorschlags' })
    expect(within(diff).getByText('28 Tage.').closest('del')).not.toBeNull()
    expect(within(diff).getByText('30 Tage.').closest('ins')).not.toBeNull()
    expect(within(diff).getAllByText('entfernt:')).toHaveLength(1)
    expect(within(diff).getAllByText('hinzugefügt:')).toHaveLength(1)
    expect(screen.getByText('Die Frist ist jetzt 30 Tage.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Annehmen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/proposals/${detail.id}/accept`)[0]?.body).toEqual({
        version: 1,
      }),
    )
  })

  test('rejecting takes an optional reason', async () => {
    const detail = makeProposalDetail({ space_id: space.id })
    const api = proposalApi('moderator', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
      'POST /api/proposals/:id/reject': { ...detail, state: 'rejected', version: 2 },
    })
    const { user } = await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    await user.click(await screen.findByRole('button', { name: 'Ablehnen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Begründung (freiwillig)'), 'Stimmt nicht.')
    await user.click(within(dialog).getByRole('button', { name: 'Ablehnen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/proposals/${detail.id}/reject`)[0]?.body).toEqual({
        version: 1,
        reason: 'Stimmt nicht.',
      }),
    )
  })

  test('the page moved on: the merged text is shown, edited and accepted again', async () => {
    const detail = makeProposalDetail({ space_id: space.id, base_version: 3 })
    const outdated = apiError(409, 'proposal.base_outdated', 'outdated', {
      current_version: 9,
      too_large: false,
      merged_content: '# Urlaub\n\n30 Tage.\n\nAntrag im Portal.',
      segments: [{ kind: 'clean', lines: ['# Urlaub', '', '30 Tage.', '', 'Antrag im Portal.'] }],
    })
    const api = proposalApi('moderator', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
      'GET /api/pages/:id/versions': page([]),
      'POST /api/proposals/:id/accept': (call: { body: unknown }) =>
        (call.body as { merged_content?: string }).merged_content
          ? { ...detail, state: 'accepted' }
          : outdated,
    })
    const { user } = await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    await user.click(await screen.findByRole('button', { name: 'Annehmen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Die Seite hat sich geändert' })
    const text = within(dialog).getByLabelText('Zusammengeführter Text')
    expect(text).toHaveValue('# Urlaub\n\n30 Tage.\n\nAntrag im Portal.')
    await user.type(text, ' Danke.')
    await user.click(within(dialog).getByRole('button', { name: 'Zusammengeführt annehmen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/proposals/${detail.id}/accept`)[1]?.body).toEqual({
        version: 1,
        merged_content: '# Urlaub\n\n30 Tage.\n\nAntrag im Portal. Danke.',
        page_version: 9,
      }),
    )
  })

  test('conflict regions are resolved by choice, never silently', async () => {
    const detail = makeProposalDetail({
      space_id: space.id,
      current_content_md: '# Urlaub\n\n31 Tage.',
      page_version: 9,
      merge: {
        clean: false,
        merged_content: null,
        segments: [
          { kind: 'clean', lines: ['# Urlaub', ''], base: [], proposed: [], current: [] },
          {
            kind: 'conflict',
            lines: [],
            base: ['28 Tage.'],
            proposed: ['30 Tage.'],
            current: ['31 Tage.'],
          },
        ],
      },
    })
    const api = proposalApi('moderator', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
      'GET /api/pages/:id/versions': page([]),
      'POST /api/proposals/:id/accept': { ...detail, state: 'accepted' },
    })
    const { user } = await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    expect(
      await screen.findByText(/Die Seite hat sich seit dem Vorschlag geändert/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Annehmen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Die Seite hat sich geändert' })
    const region = within(dialog).getByRole('group', { name: 'Konflikt 1' })
    expect(within(region).getByText('31 Tage.')).toBeInTheDocument()
    const text = within(dialog).getByLabelText('Zusammengeführter Text')
    expect(text).toHaveValue('# Urlaub\n\n31 Tage.')
    await user.click(within(region).getByRole('radio', { name: 'Vorschlag übernehmen' }))
    expect(text).toHaveValue('# Urlaub\n\n30 Tage.')
    await user.click(within(dialog).getByRole('button', { name: 'Zusammengeführt annehmen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/proposals/${detail.id}/accept`)[0]?.body).toEqual({
        version: 1,
        merged_content: '# Urlaub\n\n30 Tage.',
        page_version: 9,
      }),
    )
  })

  test('a refused decision says why', async () => {
    const detail = makeProposalDetail({ space_id: space.id })
    proposalApi('moderator', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
      'POST /api/proposals/:id/accept': apiError(409, 'proposal.page_no_ai'),
    })
    const { user } = await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    await user.click(await screen.findByRole('button', { name: 'Annehmen' }))
    expect(await screen.findByText(/für KI gesperrt/)).toBeInTheDocument()
  })

  test('editors see proposals without deciding; viewers have no tab', async () => {
    const detail = makeProposalDetail({ space_id: space.id })
    proposalApi('editor', {
      'GET /api/spaces/:id/proposals': page([detail]),
      'GET /api/proposals/:id': detail,
    })
    await renderApp(`/spaces/${space.id}/proposals/${detail.id}`)
    expect(
      await screen.findByRole('region', { name: 'Änderungen des Vorschlags' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Annehmen' })).not.toBeInTheDocument()
  })

  test('a viewer has no proposals tab and never asks', async () => {
    const api = proposalApi('viewer')
    await renderApp(`/spaces/${space.id}`)
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    expect(within(tabs).queryByRole('link', { name: /Vorschläge/ })).not.toBeInTheDocument()
    expect(api.find('GET', `/api/spaces/${space.id}/proposals`)).toHaveLength(0)
  })

  test('a page with open proposals says so', async () => {
    const one = makeProposal({ space_id: space.id, page_id: urlaub.id })
    proposalApi('editor', { 'GET /api/spaces/:id/proposals': page([one]) })
    await renderApp(`/spaces/${space.id}/p/urlaub`)
    const hint = await screen.findByRole('link', { name: /1 offener Vorschlag zu dieser Seite/ })
    expect(hint).toHaveAttribute('href', `/spaces/${space.id}/proposals`)
  })
})
