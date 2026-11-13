import { act, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import * as Y from 'yjs'
import { makePage } from '@/test/api'
import { renderApp } from '@/test/render'
import { fake, join, liveApi, space, typeInto } from './fakeLive.test-helper'

const { connections, events } = fake

vi.mock('./connect', async (original) => ({
  ...(await original<typeof import('./connect')>()),
  connectLive: (await import('./fakeLive.test-helper')).fakeConnectLive,
}))

beforeEach(() => fake.reset())

/** The live editor on a page, joined, with `text` typed (sent, not yet stored). */
async function typed(text: string) {
  const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
  liveApi('editor', () => current)
  const { router } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
  await waitFor(() => expect(connections).toHaveLength(1))
  const connection = connections[0]!
  join(connection)
  typeInto(connection.doc, text)
  const leave = () =>
    act(() => void router.navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } }))
  return { router, connection, leave }
}

// Review M2 T5, U9: leaving saves first and asks only while a change is still not
// confirmed as stored, and the question says why.
describe('leaving the live editor', () => {
  test('right after a change: it is saved first, and nothing is asked once confirmed', async () => {
    const { router, leave } = await typed('neuer Satz')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    leave()
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}`))
    expect(events).toContain('flushed')
    expect(confirm).not.toHaveBeenCalled()
  })

  test('without a change nothing is saved or asked', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    liveApi('editor', () => current)
    const { router } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    const confirm = vi.spyOn(window, 'confirm')
    act(() => void router.navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}`))
    expect(events).not.toContain('flushed')
    expect(confirm).not.toHaveBeenCalled()
  })

  test('a change the server has but has not confirmed as stored: asked, so worded', async () => {
    fake.acknowledge = false // the server answers "saved" but its snapshot lacks the change
    const { router, connection, leave } = await typed('neuer Satz')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    leave()
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    expect(confirm.mock.calls[0]![0]).toMatch(/noch nicht bestätigt/)
    expect(router.state.location.search).toEqual({ view: 'live' })
    // The server stored it and says so: leaving asks nothing.
    act(() => connection.handlers.onStored(Y.encodeSnapshot(Y.snapshot(connection.doc))))
    leave()
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}`))
    expect(confirm).toHaveBeenCalledTimes(1)
  })

  test('a change that has not reached the server: asked, so worded', async () => {
    fake.finishAnswer = () => false
    const { connection, leave } = await typed('neuer Satz')
    act(() => connection.handlers.onUnsynced(1))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    leave()
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    expect(confirm.mock.calls[0]![0]).toMatch(/noch nicht beim Server angekommen/)
  })

  test('a state that cannot be saved: asked, so worded', async () => {
    fake.finishAnswer = () => false
    const { router, connection, leave } = await typed('neuer Satz')
    act(() =>
      connection.handlers.onUnrepresentable({
        kind: 'markdown',
        block: 0,
        through: null,
        detail: null,
      }),
    )
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    leave()
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    expect(confirm.mock.calls[0]![0]).toMatch(/lässt sich nicht speichern/)
    expect(router.state.location.search).toEqual({ view: 'live' })
  })
})
