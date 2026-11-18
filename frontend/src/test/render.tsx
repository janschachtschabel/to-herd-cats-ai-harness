import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Providers } from '@/app/providers'
import { createQueryClient } from '@/app/queryClient'
import { createAppRouter } from '@/app/router/router'

/** How long the first visit of a lazy route may take to import its page (see below). */
const ROUTE_IMPORT_MS = 4_000

/** The whole app at `path`, with the real router, against the mocked API. */
export async function renderApp(path: string) {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } })
  const history = createMemoryHistory({ initialEntries: [path] })
  const router = createAppRouter(queryClient, history)
  const user = userEvent.setup()
  render(
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>,
  )
  // The router stays pending while a route's loader imports its lazy page. The first
  // visit in a test file pays for vitest's on-demand transform of that module tree:
  // 0.4 to 0.8 s on a loaded machine and past waitFor's default second on a busy one,
  // where later visits take 0.05 s. Wait for it, within the test's own 5 s.
  await waitFor(() => expect(router.state.status).toBe('idle'), { timeout: ROUTE_IMPORT_MS })
  return { router, user, queryClient, screen }
}
