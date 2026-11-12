import type { QueryClient } from '@tanstack/react-query'
import {
  createRootRouteWithContext,
  createRoute,
  notFound,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/app/shell/AppShell'
import { adminLinks } from '@/app/shell/nav'
import { LoginPage } from '@/features/auth/LoginPage'
import { hasPermission, meQuery } from '@/features/auth/queries'
import type { Me, Permission } from '@/lib/api'
import { NotFoundPage } from './NotFoundPage'
import { PendingPage } from './PendingPage'

export interface RouterContext {
  queryClient: QueryClient
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: NotFoundPage,
})

/** Where to go after logging in: only paths inside this app. */
function safeRedirect(value: unknown): string | undefined {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : undefined
}

const loginRoute = createRoute({
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
const appRoute = createRoute({
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

const indexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/spaces' })
  },
})

const spacesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/spaces',
  component: () => <PendingPage titleKey="spaces.title" />,
})

const spaceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/spaces/$spaceId',
  component: () => <PendingPage titleKey="spaces.title" />,
})

/** A page someone without the right must not even learn exists: not found. */
function requirePermission(me: Me, permission: Permission): void {
  if (!hasPermission(me, permission)) throw notFound()
}

const adminRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/admin',
  loader: ({ context }) => {
    if (adminLinks(context.me).length === 0) throw notFound()
  },
  component: Outlet,
})

const adminIndexRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/',
  beforeLoad: ({ context }) => {
    const first = adminLinks(context.me)[0]
    if (!first) throw notFound()
    throw redirect({ to: first.to })
  },
})

const usersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/users',
  loader: ({ context }) => requirePermission(context.me, 'user.manage'),
  component: () => <PendingPage titleKey="users.title" />,
})

const groupsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/groups',
  loader: ({ context }) => requirePermission(context.me, 'group.manage'),
  component: () => <PendingPage titleKey="groups.title" />,
})

const groupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/groups/$groupId',
  loader: ({ context }) => requirePermission(context.me, 'group.manage'),
  component: () => <PendingPage titleKey="groups.title" />,
})

const auditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/audit',
  loader: ({ context }) => requirePermission(context.me, 'audit.read'),
  component: () => <PendingPage titleKey="audit.title" />,
})

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    spacesRoute,
    spaceRoute,
    adminRoute.addChildren([adminIndexRoute, usersRoute, groupsRoute, groupRoute, auditRoute]),
  ]),
])
