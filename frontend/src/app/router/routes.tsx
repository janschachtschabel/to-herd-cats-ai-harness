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
import { pageQuery } from '@/features/wiki/queries'
import type { Me, Permission } from '@/lib/api'
import { NotFoundPage } from './NotFoundPage'
import { ticketSearch } from '@/features/tickets/filters'
import { messageSearch, pageSearch, safeRedirect } from './search'

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
const TagsPage = lazyRouteComponent(() => import('@/features/admin/tags/TagsPage'), 'TagsPage')
const AuditPage = lazyRouteComponent(() => import('@/features/admin/audit/AuditPage'), 'AuditPage')
const DmInspectPage = lazyRouteComponent(
  () => import('@/features/admin/dm-inspect/DmInspectPage'),
  'DmInspectPage',
)
const ConversationScreen = lazyRouteComponent(
  () => import('@/features/messaging/conversation/ConversationScreen'),
  'ConversationScreen',
)
const TicketsPage = lazyRouteComponent(
  () => import('@/features/tickets/TicketsPage'),
  'TicketsPage',
)
const TicketScreen = lazyRouteComponent(
  () => import('@/features/tickets/TicketScreen'),
  'TicketScreen',
)
const ActivityPage = lazyRouteComponent(
  () => import('@/features/activity/ActivityPage'),
  'ActivityPage',
)

export interface RouterContext {
  queryClient: QueryClient
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: NotFoundPage,
})

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

/** A page by its path (`/spaces/<id>/p/handbuch/urlaub`); `?view=` opens an editor or
 *  the version history, `?discussion=true` the discussion (at `thread`, `message`). */
const pageRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/p/$',
  validateSearch: pageSearch,
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

/** A page by its id, for links into its discussion (search hits, the activity):
 *  looks the page up and goes to its path with the discussion open. */
const pageByIdRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/go/page/$pageId',
  validateSearch: messageSearch,
  loaderDeps: ({ search }) => search,
  loader: async ({ context, params, deps }) => {
    const page = await context.queryClient.fetchQuery(pageQuery(params.pageId)).catch(() => {
      throw notFound()
    })
    throw redirect({
      to: '/spaces/$spaceId/p/$',
      params: { spaceId: page.space_id, _splat: page.path },
      search: { discussion: true, ...deps },
      replace: true,
    })
  },
})

/** A channel or direct message; `thread` opens a thread beside it. */
const conversationRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/c/$conversationId',
  validateSearch: messageSearch,
  loader: () => ConversationScreen.preload?.(),
  component: function ConversationRoute() {
    const { conversationId } = conversationRoute.useParams()
    const { thread, message } = conversationRoute.useSearch()
    return <ConversationScreen conversationId={conversationId} thread={thread} message={message} />
  },
})

/** Tickets across spaces; without filters "my tickets" (filters stand in the address). */
const ticketsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/tickets',
  validateSearch: ticketSearch,
  loader: () => TicketsPage.preload?.(),
  component: function TicketsRoute() {
    const search = ticketsRoute.useSearch()
    const navigate = ticketsRoute.useNavigate()
    return (
      <TicketsPage
        search={search}
        onSearch={(next) => void navigate({ search: next, replace: true })}
      />
    )
  },
})

/** A ticket by its number (`/tickets/42`); `thread`/`message` as for conversations. */
const ticketRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/tickets/$number',
  validateSearch: messageSearch,
  loader: ({ params }) => {
    if (!/^[1-9]\d{0,8}$/.test(params.number)) throw notFound()
    return TicketScreen.preload?.()
  },
  component: function TicketRoute() {
    const { number } = ticketRoute.useParams()
    const { thread, message } = ticketRoute.useSearch()
    return <TicketScreen number={Number(number)} thread={thread} message={message} />
  },
})

const activityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/activity',
  component: ActivityPage,
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

const tagsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/tags',
  loader: ({ context }) => requirePermission(context.me, 'tag.manage'),
  component: TagsPage,
})

const auditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/audit',
  loader: ({ context }) => requirePermission(context.me, 'audit.read'),
  component: AuditPage,
})

const dmInspectRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/dm-inspect',
  loader: ({ context }) => requirePermission(context.me, 'dm.inspect'),
  component: DmInspectPage,
})

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    spacesRoute,
    spaceRoute.addChildren([spaceIndexRoute, pageRoute, trashRoute, spaceSettingsRoute]),
    pageByIdRoute,
    conversationRoute,
    ticketsRoute,
    ticketRoute,
    activityRoute,
    profileRoute,
    adminRoute.addChildren([
      adminIndexRoute,
      usersRoute,
      groupsRoute,
      groupRoute,
      tagsRoute,
      auditRoute,
      dmInspectRoute,
    ]),
  ]),
])
