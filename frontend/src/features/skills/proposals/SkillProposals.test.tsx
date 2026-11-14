import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, makeSpace, mockApi, page, type Call } from '@/test/api'
import { renderApp } from '@/test/render'
import { makeRun } from '@/test/runs'
import { makeSkillProposal, makeSkillProposalDetail } from '@/test/skills'

const space = makeSpace({ name: 'Handbuch', my_role: 'moderator' })
const moderator = makeMe(['ai.use', 'directory.read'])
const admin = makeMe(['skill.manage', 'ai.use', 'directory.read'])

function spaceRoutes(extra: Record<string, unknown> = {}) {
  return {
    'GET /api/spaces': page([space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/proposals': page([]),
    'GET /api/skills': page([]),
    ...extra,
  }
}

describe('skill proposals', () => {
  test("a space's moderators find them beside the skills, with the AI mark", async () => {
    const proposal = makeSkillProposal({ space_id: space.id, kind: 'new', name: 'vorlage' })
    const api = mockApi({
      'GET /api/auth/me': moderator,
      'GET /api/skill-proposals': page([proposal]),
      ...spaceRoutes(),
    })
    const { user, router } = await renderApp(`/spaces/${space.id}/skills`)
    const views = await screen.findByRole('navigation', { name: 'Skills und Vorschläge' })
    const tab = within(views).getByRole('link', { name: /Vorschläge/ })
    expect(await within(tab).findByLabelText('1 offener Vorschlag')).toBeInTheDocument()
    await user.click(tab)
    const list = await screen.findByRole('list', { name: 'Vorschläge für Skills' })
    const item = within(list).getByRole('listitem')
    expect(item).toHaveTextContent('Neuer Skill „vorlage“')
    expect(item).toHaveTextContent('Die Vorlage fehlt.')
    expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    const asked = api.find('GET', '/api/skill-proposals').at(-1)!
    expect(asked.query.get('space_id')).toBe(space.id)
    expect(asked.query.get('state')).toBe('open')
    await user.selectOptions(screen.getByLabelText('Zustand'), 'Abgelehnt')
    await waitFor(() =>
      expect(api.find('GET', '/api/skill-proposals').at(-1)?.query.get('state')).toBe('rejected'),
    )
    await user.selectOptions(screen.getByLabelText('Zustand'), 'Offen')
    const again = await screen.findByRole('list', { name: 'Vorschläge für Skills' })
    await user.click(within(again).getByRole('link', { name: 'Neuer Skill „vorlage“' }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/skill-proposals/${proposal.id}`),
    )
  })

  test('people who may not decide see no proposals view', async () => {
    const editorSpace = { ...space, my_role: 'editor' as const }
    const api = mockApi({
      'GET /api/auth/me': moderator,
      ...spaceRoutes({
        'GET /api/spaces/:id': editorSpace,
        'GET /api/spaces': page([editorSpace]),
      }),
    })
    await renderApp(`/spaces/${space.id}/skills`)
    expect(await screen.findByText('Noch keine Skills.')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Skills und Vorschläge' })).toBeNull()
    expect(api.find('GET', '/api/skill-proposals')).toHaveLength(0)
  })

  test('the administration lists organisation-wide ones too', async () => {
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/spaces': page([space]),
      'GET /api/skills': page([]),
      'GET /api/skill-proposals': page([makeSkillProposal({ name: 'protokoll' })]),
    })
    const { user } = await renderApp('/admin/skills?view=proposals')
    const list = await screen.findByRole('list', { name: 'Vorschläge für Skills' })
    expect(within(list).getByText('Organisationsweit')).toBeInTheDocument()
    expect(within(list).getByRole('link', { name: 'Änderung an „protokoll“' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Wo'), 'Organisationsweit')
    await waitFor(() =>
      expect(api.find('GET', '/api/skill-proposals').at(-1)?.query.get('org_wide')).toBe('true'),
    )
  })

  test('a change: the diff, the reason and the run; a moderator accepts it', async () => {
    const proposal = makeSkillProposalDetail({ run_id: 'run-7' })
    const accepted = { ...proposal, state: 'accepted' as const, version: 2 }
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/skill-proposals/:id': proposal,
      'POST /api/skill-proposals/:id/accept': accepted,
      'GET /api/runs/:id': makeRun({ id: 'run-7', state: 'done', steps: 3 }),
    })
    const { user } = await renderApp(`/skill-proposals/${proposal.id}`)
    const title = await screen.findByRole('heading', { name: 'Änderung an „protokoll“' })
    const article = title.closest('article')!
    expect(within(article).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(within(article).getByText('Die Vorlage fehlt.')).toBeInTheDocument()
    const diff = within(article).getByRole('region', { name: 'Änderungen des Vorschlags' })
    expect(diff.querySelector('ins')).toHaveTextContent('Mit Vorlage.')
    expect(diff.querySelector('del')).toHaveTextContent('Kurz und klar.')
    expect(await within(article).findByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-7',
    )
    await user.click(within(article).getByRole('button', { name: 'Annehmen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/skill-proposals/${proposal.id}/accept`)[0]?.body).toEqual({
        version: 1,
      }),
    )
  })

  test('a skill that moved on opens the dialog with both texts; the edited text is sent', async () => {
    const proposal = makeSkillProposalDetail()
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/skill-proposals/:id': proposal,
      'POST /api/skill-proposals/:id/accept': (call: Call) =>
        (call.body as Record<string, unknown>).skill_version === undefined
          ? apiError(409, 'skill_proposal.base_outdated', 'moved', {
              skill_version: 5,
              current: { description: 'Jetzt.', content: 'Inzwischen anders.' },
              proposed: { description: 'Neu.', content: 'Mit Vorlage.' },
            })
          : { ...proposal, state: 'accepted', version: 2 },
    })
    const { user } = await renderApp(`/skill-proposals/${proposal.id}`)
    await user.click(await screen.findByRole('button', { name: 'Annehmen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Der Skill hat sich geändert' })
    const now = within(dialog).getByRole('region', { name: 'Skill jetzt' })
    expect(now).toHaveTextContent('Inzwischen anders.')
    const proposed = within(dialog).getByRole('region', { name: 'Vorschlag' })
    expect(proposed).toHaveTextContent('Mit Vorlage.')
    const content = within(dialog).getByLabelText('Anweisungen (Markdown)')
    expect(content).toHaveValue('Mit Vorlage.')
    await user.click(within(dialog).getByRole('button', { name: 'Skill jetzt übernehmen' }))
    expect(content).toHaveValue('Inzwischen anders.')
    await user.type(content, ' Plus.')
    await user.click(within(dialog).getByRole('button', { name: 'So annehmen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/skill-proposals/${proposal.id}/accept`).at(-1)?.body).toEqual({
        version: 1,
        skill_version: 5,
        description: 'Jetzt.',
        content: 'Inzwischen anders. Plus.',
      }),
    )
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  test('an open proposal that already says so opens the dialog at once', async () => {
    const proposal = makeSkillProposalDetail({
      outdated: true,
      current: { description: 'Jetzt.', content: 'Jetzt.', version: 9, number: 3 },
    })
    mockApi({ 'GET /api/auth/me': admin, 'GET /api/skill-proposals/:id': proposal })
    const { user } = await renderApp(`/skill-proposals/${proposal.id}`)
    expect(await screen.findByText(/Der Skill hat sich seit dem Vorschlag geändert/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Annehmen' }))
    expect(await screen.findByRole('dialog', { name: 'Der Skill hat sich geändert' })).toBeVisible()
  })

  test('rejecting sends the reason; refusals are put into words', async () => {
    const proposal = makeSkillProposalDetail({ kind: 'new', name: 'vorlage', current: null })
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/skill-proposals/:id': proposal,
      'POST /api/skill-proposals/:id/reject': apiError(409, 'skill_proposal.not_open'),
    })
    const { user } = await renderApp(`/skill-proposals/${proposal.id}`)
    const article = (await screen.findByRole('heading', { name: 'Neuer Skill „vorlage“' })).closest(
      'article',
    )!
    // A new skill shows its proposed text.
    expect(within(article).getByRole('heading', { name: 'Protokoll' })).toBeInTheDocument()
    await user.click(within(article).getByRole('button', { name: 'Ablehnen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Begründung (freiwillig)'), 'Nicht nötig')
    await user.click(within(dialog).getByRole('button', { name: 'Ablehnen' }))
    expect(
      await within(dialog).findByText('Über diesen Vorschlag wurde schon entschieden.'),
    ).toBeInTheDocument()
    expect(api.find('POST', `/api/skill-proposals/${proposal.id}/reject`)[0]?.body).toEqual({
      version: 1,
      reason: 'Nicht nötig',
    })
  })

  test('a decided proposal names who decided and why; nobody gets actions', async () => {
    const proposal = makeSkillProposalDetail({
      state: 'rejected',
      decided_by: { type: 'user', id: 'u', name: 'Lea Löwe' },
      decided_at: '2026-11-14T10:00:00Z',
      decision_reason: 'Passt nicht',
    })
    mockApi({ 'GET /api/auth/me': admin, 'GET /api/skill-proposals/:id': proposal })
    await renderApp(`/skill-proposals/${proposal.id}`)
    expect(await screen.findByText(/Abgelehnt von Lea Löwe/)).toBeInTheDocument()
    expect(screen.getByText('Begründung: Passt nicht')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Annehmen' })).toBeNull()
  })

  test('an author who may not decide reads it without actions; unknown ones say so', async () => {
    const proposal = makeSkillProposalDetail({ space_id: space.id })
    const viewerSpace = { ...space, my_role: 'editor' as const }
    mockApi({
      'GET /api/auth/me': moderator,
      'GET /api/spaces/:id': viewerSpace,
      'GET /api/skill-proposals/:id': (_call: Call, params: Record<string, string>) =>
        params.id === proposal.id ? proposal : apiError(404, 'skill_proposal.not_found'),
    })
    await renderApp(`/skill-proposals/${proposal.id}`)
    expect(await screen.findByRole('heading', { name: 'Änderung an „protokoll“' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Annehmen' })).toBeNull()
  })

  test('an unknown proposal says so', async () => {
    mockApi({
      'GET /api/auth/me': admin,
      'GET /api/skill-proposals/:id': apiError(404, 'skill_proposal.not_found'),
    })
    await renderApp('/skill-proposals/00000000-0000-7000-8000-000000000999')
    expect(
      await screen.findByText('Diesen Vorschlag für einen Skill gibt es nicht (mehr).'),
    ).toBeInTheDocument()
  })
})
