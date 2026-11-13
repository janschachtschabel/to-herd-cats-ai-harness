import type { QueryClient } from '@tanstack/react-query'
import {
  createRootRouteWithContext,
  createRoute,
  lazyRouteComponent,
  notFound,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/app/shell/AppShell'
import { adminLinks } from '@/app/shell/nav'
import { hasPermission, meQuery } from '@/features/auth/queries'
import type { PageMode } from '@/features/wiki/PageScreen'
import type { Me, Permission } from '@/lib/api'
import { NotFoundPage } from './NotFoundPage'

// Every page is its own chunk, loaded when its route is entered or hovered (intent
// preload), so the first load carries only the shell and the page in view.
const LoginPage = lazyRouteComponent(() => import('@/features/auth/LoginPage'), 'LoginPage')
const SpacesPage = lazyRouteComponent(() => import('@/features/spaces/SpacesPage'), 'SpacesPage')
const SpacePage = lazyRouteComponent(() => import('@/features/spaces/SpacePage'), 'SpacePage')
const WikiLayout = lazyRouteComponent(() => import('@/features/wiki/WikiLayout'), 'WikiLayout')
const WikiHome = lazyRouteComponent(() => import('@/features/wiki/WikiHome'), 'WikiHome')
const PageScreen = lazyRouteComponent(() => import('@/features/wiki/PageScreen'), 'PageScreen')
const TrashPage = lazyRouteComponent(() => import('@/features/wiki/trash/TrashPage'), 'TrashPage')
const UsersPage = lazyRouteComponent(() => import('@/features/admin/users/UsersPage'), 'UsersPage')
const GroupsPage = lazyRouteComponent(
  () => import('@/features/admin/groups/GroupsPage'),
  'GroupsPage',
)
const GroupPage = lazyRouteComponent(() => import('@/features/admin/groups/GroupPage'), 'GroupPage')
const ProfilePage = lazyRouteComponent(
  () => import('@/features/profile/ProfilePage'),
  'ProfilePage',
)
const AuditPage = lazyRouteComponent(() => import('@/features/admin/audit/AuditPage'), 'AuditPage')

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
  component: SpacesPage,
})

/** A space: its wiki (tree on the left), with the pages, the trash and the settings. */
const spaceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/spaces/$spaceId',
  // The layout takes the id as a prop, so the route component wraps it; load it here.
  loader: () => WikiLayout.preload?.(),
  component: function SpaceRoute() {
    const { spaceId } = spaceRoute.useParams()
    return <WikiLayout spaceId={spaceId} />
  },
})

const spaceIndexRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/',
  component: WikiHome,
})

const PAGE_MODES: readonly PageMode[] = ['edit', 'live', 'versions']

/** A page by its path (`/spaces/<id>/p/handbuch/urlaub`); `?view=` opens an editor or
 *  the version history. */
const pageRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/p/$',
  validateSearch: (search: Record<string, unknown>): { view?: PageMode } =>
    PAGE_MODES.includes(search.view as PageMode) ? { view: search.view as PageMode } : {},
  loader: () => PageScreen.preload?.(),
  component: function PageRoute() {
    const { _splat } = pageRoute.useParams()
    const { view } = pageRoute.useSearch()
    return <PageScreen path={_splat ?? ''} mode={view} />
  },
})

const trashRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/trash',
  component: TrashPage,
})

const spaceSettingsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/settings',
  loader: () => SpacePage.preload?.(),
  component: function SpaceSettingsRoute() {
    const { spaceId } = spaceSettingsRoute.useParams()
    return <SpacePage spaceId={spaceId} />
  },
})

const profileRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/profile',
  component: ProfilePage,
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
  component: UsersPage,
})

const groupsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/groups',
  loader: ({ context }) => requirePermission(context.me, 'group.manage'),
  component: GroupsPage,
})

const groupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/groups/$groupId',
  loader: async ({ context }) => {
    requirePermission(context.me, 'group.manage')
    await GroupPage.preload?.()
  },
  component: function GroupRoute() {
    const { groupId } = groupRoute.useParams()
    return <GroupPage groupId={groupId} />
  },
})

const auditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/audit',
  loader: ({ context }) => requirePermission(context.me, 'audit.read'),
  component: AuditPage,
})

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    spacesRoute,
    spaceRoute.addChildren([spaceIndexRoute, pageRoute, trashRoute, spaceSettingsRoute]),
    profileRoute,
    adminRoute.addChildren([adminIndexRoute, usersRoute, groupsRoute, groupRoute, auditRoute]),
  ]),
])
