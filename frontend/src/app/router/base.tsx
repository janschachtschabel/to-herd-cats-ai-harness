import type { QueryClient } from '@tanstack/react-query'
import {
  createRootRouteWithContext,
  createRoute,
  lazyRouteComponent,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/app/shell/AppShell'
import { meQuery } from '@/features/auth/queries'
import { MaintenanceGate } from '@/features/shared/MaintenancePage'
import { NotFoundPage } from './NotFoundPage'
import { safeRedirect, secondFactor, signInError, type LoginSearch } from './search'

const LoginPage = lazyRouteComponent(() => import('@/features/auth/LoginPage'), 'LoginPage')

export interface RouterContext {
  queryClient: QueryClient
}

export const rootRoute = createRootRouteWithContext<RouterContext>()({
  // In maintenance (a request answered 503 `maintenance.active`) the whole window waits.
  component: () => (
    <MaintenanceGate>
      <Outlet />
    </MaintenanceGate>
  ),
  notFoundComponent: NotFoundPage,
})

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  // Every key always comes back, undefined when refused: TanStack Router lays the result
  // over the raw search, so a key left out would keep its unchecked value.
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: safeRedirect(search.redirect),
    error: signInError(search.error),
    second_factor: secondFactor(search.second_factor),
  }),
  beforeLoad: async ({ context, search }) => {
    const me = await context.queryClient.ensureQueryData(meQuery)
    if (me) throw redirect({ to: search.redirect ?? '/spaces' })
  },
  component: LoginPage,
})

/** Everything behind the login, inside the shell. */
export const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'app',
  beforeLoad: async ({ context, location }) => {
    const me = await context.queryClient.ensureQueryData(meQuery)
    if (!me) throw redirect({ to: '/login', search: { redirect: location.href } })
    return { me }
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
  notFoundComponent: NotFoundPage,
})
