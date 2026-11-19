import type { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'
import { createElement } from 'react'
import { meQuery } from '@/features/auth/queries'
import { showMaintenance } from '@/features/shared/maintenance'
import { LoadingState } from '@/features/shared/states'
import { onMaintenance, onUnauthorized } from '@/lib/api'
import { routeTree } from './routes'

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  const router = createRouter({
    routeTree,
    context: { queryClient },
    history,
    defaultPreload: 'intent',
    // Shown while a page's code or data takes longer than a moment (pages load lazily).
    defaultPendingComponent: () => createElement(LoadingState),
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
  // A request answered 503 `maintenance.active`: the maintenance page until it ends.
  onMaintenance(showMaintenance)
  return router
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
