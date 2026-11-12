import type { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'
import { meQuery } from '@/features/auth/queries'
import { onUnauthorized } from '@/lib/api'
import { routeTree } from './routes'

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  const router = createRouter({
    routeTree,
    context: { queryClient },
    history,
    defaultPreload: 'intent',
    scrollRestoration: true,
  })
  // A request answered 401 means the session is gone: back to the login, and back here after.
  onUnauthorized(() => {
    queryClient.setQueryData(meQuery.queryKey, null)
    const here = router.state.location
    if (here.pathname !== '/login') {
      void router.navigate({ to: '/login', search: { redirect: here.href } })
    }
  })
  return router
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
