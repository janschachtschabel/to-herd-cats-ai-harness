import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import type { SpaceRole, WikiPage } from '@/lib/api'
import {
  apiError,
  makeAttachment,
  makeMe,
  makePage,
  makeSpace,
  makeVersion,
  mockApi,
  nodeOf,
  page,
} from '@/test/api'
import { renderApp } from '@/test/render'

/** Chooses a file in the input. jsdom's File is not a body the test's fetch accepts
 *  (a browser's is), and user-event only takes jsdom's: a fetch Blob with a name. */
async function choose(input: HTMLElement, text: string, name: string) {
  const file = Object.assign(await new Response(text).blob(), { name })
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  fireEvent.change(input)
}

const space = makeSpace({ name: 'Handbuch', my_role: 'editor' })

function wikiApi(role: SpaceRole, current: () => WikiPage, extra = {}) {
  const roleSpace = { ...space, my_role: role }
  return mockApi({
    'GET /api/auth/me': makeMe(role === 'admin' ? ['page.purge'] : []),
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    'GET /api/spaces/:id/pages/tree': () => page([nodeOf(current())]),
    'GET /api/spaces/:id/pages/by-path': () => current(),
    'GET /api/pages/:id': () => current(),
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    ...extra,
  })
}

describe('wiki editing', () => {
  test('conflict dialog keeps my text', async () => {
    let server = makePage({ space_id: space.id, content_md: 'alt', version: 1 })
    const api = wikiApi('editor', () => server, {
      'PATCH /api/pages/:id': (call: { body: unknown }) => {
        const body = call.body as { version: number; content_md?: string }
        if (body.version !== server.version) return apiError(409, 'page.version_conflict')
        server = {
          ...server,
          content_md: body.content_md ?? server.content_md,
          version: server.version + 1,
        }
        return server
      },
    })
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=edit`)
    const form = await screen.findByRole('form', { name: 'Seite bearbeiten' })
    const text = within(form).getByLabelText('Markdown')
    await user.clear(text)
    await user.type(text, 'meins')
    // Meanwhile someone else saved.
    server = { ...server, content_md: 'fremd', version: 2 }
    await user.click(within(form).getByRole('button', { name: 'Speichern' }))
    const dialog = await screen.findByRole('dialog', {
      name: 'Die Seite wurde inzwischen geändert',
    })
    await user.click(within(dialog).getByRole('button', { name: 'Meine Fassung behalten' }))
    expect(await screen.findByText(/dein Text ist erhalten/)).toBeInTheDocument()
    expect(text).toHaveValue('meins')
    await user.click(within(form).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(router.state.location.search).toEqual({}))
    expect(api.find('PATCH', `/api/pages/${server.id}`).map((c) => c.body)).toEqual([
      { content_md: 'meins', version: 1 },
      { content_md: 'meins', version: 2 },
    ])
    expect(server.content_md).toBe('meins')
  })

  test('conflict dialog can discard my text for the current version', async () => {
    let server = makePage({ space_id: space.id, content_md: 'alt', version: 1 })
    wikiApi('editor', () => server, {
      'PATCH /api/pages/:id': apiError(409, 'page.version_conflict'),
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=edit`)
    const text = await screen.findByLabelText('Markdown')
    await user.type(text, ' und mehr')
    server = { ...server, content_md: 'fremd', version: 2 }
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    await user.click(await screen.findByRole('button', { name: 'Meine Änderungen verwerfen' }))
    await waitFor(() => expect(text).toHaveValue('fremd'))
  })

  test('leaving with unsaved changes asks first', async () => {
    const server = makePage({ space_id: space.id, content_md: 'alt' })
    wikiApi('editor', () => server)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=edit`)
    await user.type(await screen.findByLabelText('Markdown'), '!')
    await user.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(confirm).toHaveBeenCalledWith(
      'Deine Änderungen sind nicht gespeichert. Trotzdem verlassen?',
    )
    expect(router.state.location.search).toEqual({ view: 'edit' })
  })

  test('versions show the diff and restore with the page version', async () => {
    const server = makePage({ space_id: space.id, version: 4 })
    const api = wikiApi('editor', () => server, {
      'GET /api/pages/:id/versions': page([
        makeVersion(2, { source: 'collab', label: 'Freigabe' }),
        makeVersion(1),
      ]),
      'GET /api/pages/:id/diff': {
        from_number: 1,
        to_number: 2,
        from_title: 'Alt',
        to_title: 'Handbuch',
        title_changed: true,
        hunks: [
          { kind: 'delete', lines: ['vorher'] },
          { kind: 'insert', lines: ['nachher'] },
        ],
      },
      'POST /api/pages/:id/versions/:n/restore': { ...server, version: 5 },
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=versions`)
    expect(await screen.findByText('nachher')).toBeInTheDocument()
    expect(screen.getByText('Titel: „Alt“ → „Handbuch“')).toBeInTheDocument()
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(api.find('GET', `/api/pages/${server.id}/diff`)[0]?.query.toString()).toBe('from=1&to=2')
    await user.click(screen.getByRole('button', { name: 'Version 1 wiederherstellen' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Wiederherstellen' }),
    )
    await waitFor(() =>
      expect(api.find('POST', `/api/pages/${server.id}/versions/1/restore`)[0]?.body).toEqual({
        version: 4,
      }),
    )
  })

  test('a diff too large to compare says so', async () => {
    const server = makePage({ space_id: space.id })
    wikiApi('viewer', () => server, {
      'GET /api/pages/:id/versions': page([makeVersion(2), makeVersion(1)]),
      'GET /api/pages/:id/diff': apiError(422, 'page.diff_too_large'),
    })
    await renderApp(`/spaces/${space.id}/p/handbuch?view=versions`)
    expect(
      await screen.findByText('Die Versionen sind zu lang für einen Vergleich.'),
    ).toBeInTheDocument()
    // Viewers compare, but neither restore nor name versions.
    expect(screen.queryByRole('button', { name: /wiederherstellen/ })).toBeNull()
  })

  test('uploading sends the raw file and translates a refused type', async () => {
    const server = makePage({ space_id: space.id })
    let refuse = true
    const api = wikiApi('editor', () => server, {
      'POST /api/pages/:id/attachments': () =>
        refuse
          ? apiError(415, 'attachment.type_mismatch')
          : { status: 201, body: makeAttachment() },
    })
    await renderApp(`/spaces/${space.id}/p/handbuch`)
    const input = await screen.findByLabelText('Datei hochladen', { selector: 'input' })
    await choose(input, '<html>', 'bild.png')
    expect(
      await screen.findByText('Die Dateiendung passt nicht zum Inhalt der Datei.'),
    ).toBeInTheDocument()
    const call = api.find('POST', `/api/pages/${server.id}/attachments`)[0]!
    expect(call.query.get('filename')).toBe('bild.png')
    expect(call.headers.get('Content-Type')).toBe('application/octet-stream')
    expect(call.body).toBe('<html>')
    refuse = false
    await choose(input, '%PDF', 'plan.pdf')
    await waitFor(() => expect(screen.queryByText(/Dateiendung/)).toBeNull())
  })

  test('the trash restores a page and explains a draft parent', async () => {
    const server = makePage({ space_id: space.id })
    const trashed = {
      ...nodeOf(makePage({ title: 'Alt', path: 'alt' })),
      trashed_at: '2026-11-12T11:00:00Z',
    }
    wikiApi('admin', () => server, {
      'GET /api/spaces/:id/trash': page([trashed]),
      'POST /api/pages/:id/restore': apiError(409, 'page.parent_draft'),
    })
    const { user } = await renderApp(`/spaces/${space.id}/trash`)
    await user.click(await screen.findByRole('button', { name: '„Alt“ wiederherstellen' }))
    expect(await screen.findByText(/noch ein Entwurf/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '„Alt“ endgültig löschen' })).toBeInTheDocument()
  })
})
