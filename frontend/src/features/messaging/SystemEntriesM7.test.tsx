import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SystemEntry } from '@/lib/api'
import i18n from '@/lib/i18n'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { systemText } from './display'

const t = i18n.t.bind(i18n)

function entry(key: string, actor: SystemEntry['actor'] = null): SystemEntry {
  return { key, actor, number: null, old: null, new: null }
}

describe('system entries of M7', () => {
  test('a page whose review came due has no actor; an automation names its owner', async () => {
    expect(systemText(t, entry('page.review_due'))).toBe('Die Prüffrist der Seite ist abgelaufen.')
    expect(
      systemText(t, {
        ...entry('automation.started', { id: 'u', name: 'Mia Muster' }),
        automation_id: 'au-1',
      }),
    ).toBe('Aufgabe von Mia Muster gestartet.')
    await i18n.changeLanguage('en')
    expect(systemText(t, entry('page.review_due'))).toBe("The page's review is due.")
    expect(systemText(t, entry('automation.started', { id: 'u', name: 'Mia Muster' }))).toBe(
      "Mia Muster's automation started.",
    )
  })

  test('in a channel, the started automation is a thread root one can open', async () => {
    const me = makeMe(['directory.read'])
    const space = makeSpace({ id: 'space-1', my_role: 'viewer' })
    const channel = makeConversation()
    const root = makeMessage({
      conversation_id: channel.id,
      kind: 'system',
      author: null,
      body_md: '',
      reply_count: 1,
      system: {
        ...entry('automation.started', { id: 'u', name: 'Mia Muster' }),
        automation_id: 'au-1',
      },
    })
    const answer = makeMessage({
      conversation_id: channel.id,
      parent_id: root.id,
      kind: 'agent',
      author: { type: 'agent', id: 'hilda', name: 'Hilda' },
      body_md: 'Der Wochenbericht ist fertig.',
    })
    mockApi({
      ...shellRoutes(me, [space]),
      'GET /api/spaces/:id': space,
      'GET /api/conversations/:id': channel,
      'GET /api/conversations/:id/messages': page([root]),
      'POST /api/conversations/:id/read': { status: 204 },
      'GET /api/messages/:id': root,
      'GET /api/messages/:id/replies': page([answer]),
      'GET /api/runs/:id/events': page([]),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    expect(await screen.findByText('Aufgabe von Mia Muster gestartet.')).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', {
        name: 'Thread „Aufgabe von Mia Muster gestartet.“ öffnen, 1 Antwort',
      }),
    )
    const thread = await screen.findByRole('complementary', { name: 'Thread' })
    expect(await within(thread).findByText('Der Wochenbericht ist fertig.')).toBeInTheDocument()
  })
})
