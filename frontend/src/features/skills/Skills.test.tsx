import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { makeSkill, makeSkillDetail } from '@/test/skills'

const admin = makeMe(['skill.manage', 'ai.use', 'directory.read'])
const space = makeSpace({ name: 'Handbuch', my_role: 'moderator' })

function spaceRoutes(extra: Record<string, unknown> = {}) {
  return {
    'GET /api/spaces': page([space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/proposals': page([]),
    ...extra,
  }
}

describe('skills', () => {
  test('the administration lists them with filters and creates one with a preview', async () => {
    const org = makeSkill({ name: 'protokoll' })
    const created = makeSkillDetail({ name: 'kurz', description: 'Fasst kurz.' })
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/spaces': page([space]),
      'GET /api/skills': page([org]),
      'POST /api/skills': { status: 201, body: created },
      'GET /api/skills/:id': created,
      'GET /api/skills/:id/versions': page([]),
    })
    const { user, router } = await renderApp('/admin/skills')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(within(nav).getByRole('link', { name: 'Skills' })).toBeInTheDocument()
    const list = await screen.findByRole('list', { name: 'Skills' })
    expect(within(list).getByRole('link', { name: 'protokoll' })).toBeInTheDocument()
    expect(within(list).getByText('Organisationsweit')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Zustand'), 'Archiviert')
    await waitFor(() =>
      expect(api.find('GET', '/api/skills').at(-1)?.query.get('state')).toBe('archived'),
    )
    await user.selectOptions(screen.getByLabelText('Wo'), 'Handbuch')
    await waitFor(() =>
      expect(api.find('GET', '/api/skills').at(-1)?.query.get('space_id')).toBe(space.id),
    )

    await user.click(screen.getByRole('button', { name: 'Skill anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'kurz')
    await user.type(within(dialog).getByLabelText('Beschreibung'), 'Fasst kurz.')
    await user.type(within(dialog).getByLabelText('Anweisungen (Markdown)'), '# Kurz')
    await user.click(within(dialog).getByRole('tab', { name: 'Vorschau' }))
    expect(within(dialog).getByRole('heading', { name: 'Kurz' })).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/skills')[0]?.body).toEqual({
        name: 'kurz',
        description: 'Fasst kurz.',
        content: '# Kurz',
        space_id: space.id,
      }),
    )
    await waitFor(() => expect(router.state.location.pathname).toBe(`/skills/${created.id}`))
  })

  test('a skill: its text, versions with restore, archive and export', async () => {
    const skill = makeSkillDetail({ version: 3, content: '# Protokoll\n\nKurz und klar.' })
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/spaces': page([]),
      'GET /api/skills/:id': skill,
      'GET /api/skills/:id/versions': page([
        { number: 2, description: 'Neu', author: skill.author, created_at: skill.created_at },
        { number: 1, description: 'Alt', author: skill.author, created_at: skill.created_at },
      ]),
      'GET /api/skills/:id/versions/:n': {
        number: 1,
        description: 'Alt',
        author: skill.author,
        created_at: skill.created_at,
        content: '# Früher',
      },
      'POST /api/skills/:id/versions/:n/restore': { ...skill, version: 4 },
      'POST /api/skills/:id/archive': { ...skill, state: 'archived', version: 4 },
    })
    const { user } = await renderApp(`/skills/${skill.id}`)
    expect(await screen.findByRole('heading', { name: 'Protokoll' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Exportieren' })).toHaveAttribute(
      'href',
      `/api/skills/${skill.id}/export`,
    )
    const versions = await screen.findByRole('list', { name: 'Versionen' })
    await user.click(within(versions).getByRole('button', { name: 'Version 1 ansehen' }))
    expect(await screen.findByRole('heading', { name: 'Früher' })).toBeInTheDocument()
    await user.click(within(versions).getByRole('button', { name: 'Version 1 wiederherstellen' }))
    const confirm = await screen.findByRole('dialog')
    await user.click(within(confirm).getByRole('button', { name: 'Wiederherstellen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/skills/${skill.id}/versions/1/restore`)[0]?.body).toEqual({
        version: 3,
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Archivieren' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/skills/${skill.id}/archive`)[0]?.body).toEqual({
        version: 3,
      }),
    )
  })

  test('editing with a stale version offers to reload', async () => {
    const skill = makeSkillDetail()
    mockApi({
      'GET /api/auth/me': admin,
      'GET /api/spaces': page([]),
      'GET /api/skills/:id': skill,
      'GET /api/skills/:id/versions': page([]),
      'PATCH /api/skills/:id': apiError(409, 'skill.version_conflict'),
    })
    const { user } = await renderApp(`/skills/${skill.id}`)
    await user.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Beschreibung'), ' Mehr.')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(
      await within(dialog).findByRole('button', { name: 'Aktuelle Fassung laden' }),
    ).toBeInTheDocument()
  })

  test('importing shows what was created and what was skipped, and runs nothing', async () => {
    const api = mockApi({
      'GET /api/auth/me': admin,
      'GET /api/spaces': page([]),
      'GET /api/skills': page([]),
      'POST /api/skills/import': {
        created: [
          {
            path: 'protokoll/SKILL.md',
            skill_id: 's1',
            name: 'protokoll',
            ignored_fields: ['license'],
          },
        ],
        skipped: [
          { path: 'skript/run.py', reason: 'file_unsupported' },
          { path: 'kurz/SKILL.md', reason: 'exists' },
        ],
      },
    })
    const { user } = await renderApp('/admin/skills')
    await user.click(await screen.findByRole('button', { name: 'Importieren' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Nichts aus einem Skill wird ausgeführt/)).toBeInTheDocument()
    // A blob from a Response (jsdom's File is no request body for the fetch in tests).
    const file = Object.assign(await new Response('PK').blob(), { name: 'skills.zip' })
    const input = within(dialog).getByLabelText('Datei (SKILL.md oder ZIP)')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    fireEvent.change(input)
    await user.click(within(dialog).getByRole('button', { name: 'Importieren' }))
    expect(await within(dialog).findByText('protokoll')).toBeInTheDocument()
    expect(within(dialog).getByText(/Nicht übernommen: license/)).toBeInTheDocument()
    expect(
      within(dialog).getByText(/Nur die SKILL.md eines Skills wird übernommen/),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(/Diesen Namen gibt es hier schon/)).toBeInTheDocument()
    // The result keeps the note that nothing of a skill is executed.
    expect(within(dialog).getByText(/Nichts aus einem Skill wird ausgeführt/)).toBeInTheDocument()
    const call = api.find('POST', '/api/skills/import')[0]
    expect(call?.headers.get('Content-Type')).toBe('application/zip')
    expect(call?.query.get('space_id')).toBeNull()
  })

  test("a space's skills tab: moderators with AI manage, viewers read", async () => {
    const own = makeSkill({ name: 'bereichs-skill', space_id: space.id })
    const api = mockApi({
      'GET /api/auth/me': makeMe(['ai.use']),
      'GET /api/skills': page([own]),
      ...spaceRoutes(),
    })
    const { user } = await renderApp(`/spaces/${space.id}`)
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    await user.click(within(tabs).getByRole('link', { name: 'Skills' }))
    expect(await screen.findByRole('link', { name: 'bereichs-skill' })).toBeInTheDocument()
    expect(api.find('GET', '/api/skills').at(-1)?.query.get('space_id')).toBe(space.id)
    expect(screen.getByRole('button', { name: 'Skill anlegen' })).toBeInTheDocument()
  })

  test('a viewer with AI reads the tab without managing', async () => {
    const viewerSpace = { ...space, my_role: 'viewer' as const }
    mockApi({
      'GET /api/auth/me': makeMe(['ai.use']),
      'GET /api/skills': page([]),
      ...spaceRoutes({
        'GET /api/spaces/:id': viewerSpace,
        'GET /api/spaces': page([viewerSpace]),
      }),
    })
    await renderApp(`/spaces/${space.id}/skills`)
    expect(await screen.findByText('Noch keine Skills.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Skill anlegen' })).not.toBeInTheDocument()
  })

  test('without AI there is no skills tab and no skills administration', async () => {
    mockApi({ 'GET /api/auth/me': makeMe([]), ...spaceRoutes() })
    await renderApp(`/spaces/${space.id}`)
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    expect(within(tabs).queryByRole('link', { name: 'Skills' })).not.toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(within(nav).queryByRole('link', { name: 'Skills' })).not.toBeInTheDocument()
  })
})
