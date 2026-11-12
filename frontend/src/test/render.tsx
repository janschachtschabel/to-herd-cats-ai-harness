import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Providers } from '@/app/providers'
import { createQueryClient } from '@/app/queryClient'
import { createAppRouter } from '@/app/router/router'

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
  await waitFor(() => expect(router.state.status).toBe('idle'))
  return { router, user, queryClient, screen }
}
