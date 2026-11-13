import { createRoute, lazyRouteComponent, notFound, redirect } from '@tanstack/react-router'
import { pageQuery } from '@/features/wiki/queries'
import { ticketSearch } from '@/features/tickets/filters'
import { adminTree } from './adminRoutes'
import { appRoute, loginRoute, rootRoute } from './base'
import { messageSearch, pageSearch } from './search'

export type { RouterContext } from './base'

// Every page is its own chunk, loaded when its route is entered or hovered (intent
// preload), so the first load carries only the shell and the page in view.
const SpacesPage = lazyRouteComponent(() => import('@/features/spaces/SpacesPage'), 'SpacesPage')
const SpacePage = lazyRouteComponent(() => import('@/features/spaces/SpacePage'), 'SpacePage')
const WikiLayout = lazyRouteComponent(() => import('@/features/wiki/WikiLayout'), 'WikiLayout')
const WikiHome = lazyRouteComponent(() => import('@/features/wiki/WikiHome'), 'WikiHome')
const PageScreen = lazyRouteComponent(() => import('@/features/wiki/PageScreen'), 'PageScreen')
const TrashPage = lazyRouteComponent(() => import('@/features/wiki/trash/TrashPage'), 'TrashPage')
const ProfilePage = lazyRouteComponent(
  () => import('@/features/profile/ProfilePage'),
  'ProfilePage',
)
const ConversationScreen = lazyRouteComponent(
  () => import('@/features/messaging/conversation/ConversationScreen'),
  'ConversationScreen',
)
const BoardView = lazyRouteComponent(
  () => import('@/features/tickets/board/BoardView'),
  'BoardView',
)
const EpicsView = lazyRouteComponent(
  () => import('@/features/tickets/epics/EpicsView'),
  'EpicsView',
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

/** A space's tickets as a board (its statuses as columns) and its epics. */
const boardRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/board',
  component: BoardView,
})

const epicsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/epics',
  component: EpicsView,
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

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    spacesRoute,
    spaceRoute.addChildren([
      spaceIndexRoute,
      pageRoute,
      trashRoute,
      spaceSettingsRoute,
      boardRoute,
      epicsRoute,
    ]),
    pageByIdRoute,
    conversationRoute,
    ticketsRoute,
    ticketRoute,
    activityRoute,
    profileRoute,
    adminTree,
  ]),
])
