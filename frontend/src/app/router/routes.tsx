import { createRoute, lazyRouteComponent, notFound, redirect } from '@tanstack/react-router'
import { pageQuery } from '@/features/wiki/queries'
import { ticketSearch } from '@/features/tickets/filters'
import { adminTree } from './adminRoutes'
import { aiWorkRoutes } from './aiRoutes'
import { appRoute, loginRoute, rootRoute } from './base'
import { messageSearch, profileSearch } from './search'
import { skillProposalRoute, skillRoute, spaceTree } from './spaceRoutes'
import { tokenRoutes } from './tokenRoutes'

export type { RouterContext } from './base'

// Every page is its own chunk, loaded when its route is entered or hovered (intent
// preload), so the first load carries only the shell and the page in view.
const SpacesPage = lazyRouteComponent(() => import('@/features/spaces/SpacesPage'), 'SpacesPage')
const ProfilePage = lazyRouteComponent(
  () => import('@/features/profile/ProfilePage'),
  'ProfilePage',
)
const ConversationScreen = lazyRouteComponent(
  () => import('@/features/messaging/conversation/ConversationScreen'),
  'ConversationScreen',
)
const MyBoardPage = lazyRouteComponent(
  () => import('@/features/tickets/my-board/MyBoardPage'),
  'MyBoardPage',
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

/** My tickets of every space as a board by status category (plan M4b). */
const myBoardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/my-board',
  component: MyBoardPage,
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
  validateSearch: profileSearch,
  loader: () => ProfilePage.preload?.(),
  component: function ProfileRoute() {
    const { linked, link_error } = profileRoute.useSearch()
    return <ProfilePage linked={linked} linkError={link_error} />
  },
})

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    spacesRoute,
    spaceTree,
    skillRoute,
    skillProposalRoute,
    pageByIdRoute,
    conversationRoute,
    ticketsRoute,
    myBoardRoute,
    ticketRoute,
    activityRoute,
    profileRoute,
    ...tokenRoutes,
    ...aiWorkRoutes,
    adminTree,
  ]),
])
