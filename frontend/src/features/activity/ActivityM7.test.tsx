import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, makePage, mockApi, page } from '@/test/api'
import { makeActivity, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

const HILDA = { type: 'agent' as const, id: 'hilda', name: 'Hilda' }

function automationEntry(paused_reason: string | null) {
  return makeActivity({
    reason: 'automation',
    conversation: null,
    message_id: null,
    author: HILDA,
    snippet: '',
    automation: { id: `au-${paused_reason}`, paused_reason },
  })
}

describe('activity entries of M7', () => {
  test('a paused automation gets a sentence per reason and opens the automation', async () => {
    const owner = automationEntry('owner')
    mockApi({
      ...shellRoutes(makeMe(['ai.use'])),
      'POST /api/activity/:id/read': { status: 204 },
      'GET /api/automations/au-owner': apiError(404, 'automation.not_found'),
      'GET /api/automations/au-owner/firings': page([]),
      'GET /api/activity': page([
        owner,
        automationEntry('failing'),
        automationEntry('manual'),
        automationEntry(null),
      ]),
    })
    const { user, router } = await renderApp('/activity')
    const sentences = [
      'Eine Aufgabe mit Hilda ist angehalten: Die Eigentümerin darf sie nicht mehr ausführen. Wer sie anlegen dürfte, kann sie übernehmen.',
      'Eine Aufgabe mit Hilda ist angehalten: Drei Läufe in Folge kamen nicht zu Ende.',
      'Eine Aufgabe mit Hilda wurde von Hand angehalten.',
      'Eine Aufgabe mit Hilda war angehalten und läuft inzwischen wieder.',
    ]
    const items = await Promise.all(
      sentences.map(async (text) => (await screen.findByText(text)).closest('li')!),
    )
    for (const item of items) {
      expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
      expect(within(item).getByRole('button', { name: 'Öffnen' })).toBeInTheDocument()
      expect(
        within(item).getByRole('button', { name: 'Eintrag von Hilda als erledigt markieren' }),
      ).toBeInTheDocument()
    }
    await user.click(within(items[0]!).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/automations/au-owner'))
    // Gone or no longer visible: the page says so.
    expect(
      await screen.findByText('Diese Aufgabe gibt es nicht, oder du darfst sie nicht sehen.'),
    ).toBeInTheDocument()
  })

  test('a review that came due names the page and no author, and opens its thread', async () => {
    const reviewed = makePage({ id: 'p-9', title: 'Urlaubsregeln' })
    const entry = makeActivity({
      reason: 'review_due',
      author: null,
      snippet: '',
      conversation: {
        id: 'c-9',
        kind: 'thread_page',
        name: null,
        space_id: 'space-1',
        page_id: 'p-9',
        ticket_number: null,
      },
    })
    mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'GET /api/pages/:id': reviewed,
      'POST /api/activity/:id/read': { status: 204 },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText(/Prüffrist/)).closest('li')!
    await waitFor(() =>
      expect(item).toHaveTextContent(
        'Die Prüffrist der Seite „Urlaubsregeln“ ist abgelaufen. Bitte prüfen.',
      ),
    )
    expect(item).not.toHaveTextContent('Unbekannt')
    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).not.toBe('/activity'))
  })

  test('a review entry whose page cannot be read says "a page"', async () => {
    const entry = makeActivity({
      reason: 'review_due',
      author: null,
      snippet: '',
      conversation: {
        id: 'c-9',
        kind: 'thread_page',
        name: null,
        space_id: 'space-1',
        page_id: 'p-gone',
        ticket_number: null,
      },
    })
    mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'GET /api/pages/:id': apiError(404, 'page.not_found'),
    })
    await renderApp('/activity')
    expect(
      await screen.findByText('Die Prüffrist einer Seite ist abgelaufen. Bitte prüfen.'),
    ).toBeInTheDocument()
  })
})
