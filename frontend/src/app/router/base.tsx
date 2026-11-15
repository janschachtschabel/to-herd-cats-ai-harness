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
import { NotFoundPage } from './NotFoundPage'
import { safeRedirect } from './search'

const LoginPage = lazyRouteComponent(() => import('@/features/auth/LoginPage'), 'LoginPage')

export interface RouterContext {
  queryClient: QueryClient
}

export const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: NotFoundPage,
})

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => {
    const target = safeRedirect(search.redirect)
    return target ? { redirect: target } : {}
  },
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
