import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { MarkdownContent } from './MarkdownContent'

function renderMarkdown(markdown: string, onCreateMissing?: (title: string) => void) {
  const rootRoute = createRootRoute({
    component: () => (
      <MarkdownContent
        spaceId="s1"
        markdown={markdown}
        lookup={new Map([['handbuch', 'team/handbuch']])}
        onCreateMissing={onCreateMissing}
      />
    ),
  })
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  return render(<RouterProvider router={router} />)
}

describe('MarkdownContent', () => {
  test('renders no raw html from markdown', async () => {
    const { container } = renderMarkdown(
      'Hallo <script>alert(1)</script><img src=x onerror="alert(1)"> <b>fett</b>\n\n<div>block</div>',
    )
    await screen.findByText(/Hallo/)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('.wiki-prose div')).toBeNull()
  })

  test('javascript: links are not rendered as links', async () => {
    renderMarkdown('[böse](javascript:alert(1)) und [gut](https://example.com)')
    expect(await screen.findByText('böse')).not.toHaveAttribute('href')
    expect(screen.queryByRole('link', { name: 'böse' })).toBeNull()
    const good = screen.getByRole('link', { name: 'gut' })
    expect(good).toHaveAttribute('href', 'https://example.com')
    expect(good).toHaveAttribute('rel', 'noopener noreferrer')
  })

  test('wiki links open the page; missing ones offer to create it', async () => {
    const create = vi.fn()
    renderMarkdown('[[Handbuch]] und [[Neue Seite]]', create)
    expect(await screen.findByRole('link', { name: 'Handbuch' })).toHaveAttribute(
      'href',
      '/spaces/s1/p/team/handbuch',
    )
    screen.getByRole('button', { name: 'Seite „Neue Seite“ anlegen' }).click()
    expect(create).toHaveBeenCalledWith('Neue Seite')
  })

  test('gfm tables, task lists and heading anchors', async () => {
    const { container } = renderMarkdown(
      '## Über uns\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- [x] fertig',
    )
    expect(await screen.findByRole('heading', { name: 'Über uns' })).toHaveAttribute(
      'id',
      'ueber-uns',
    )
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(container.querySelector('input[type="checkbox"]')).toBeChecked()
  })
})
