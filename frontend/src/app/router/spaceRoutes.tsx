import { createRoute, lazyRouteComponent } from '@tanstack/react-router'
import { boardSearch } from '@/features/tickets/board/search'
import { appRoute } from './base'
import { pageSearch } from './search'

// A space and what it holds; every view is its own chunk (as in routes.tsx).
const WikiLayout = lazyRouteComponent(() => import('@/features/wiki/WikiLayout'), 'WikiLayout')
const WikiHome = lazyRouteComponent(() => import('@/features/wiki/WikiHome'), 'WikiHome')
const PageScreen = lazyRouteComponent(() => import('@/features/wiki/PageScreen'), 'PageScreen')
const TrashPage = lazyRouteComponent(() => import('@/features/wiki/trash/TrashPage'), 'TrashPage')
const SpacePage = lazyRouteComponent(() => import('@/features/spaces/SpacePage'), 'SpacePage')
const BoardView = lazyRouteComponent(
  () => import('@/features/tickets/board/BoardView'),
  'BoardView',
)
const EpicsView = lazyRouteComponent(
  () => import('@/features/tickets/epics/EpicsView'),
  'EpicsView',
)
const SprintsView = lazyRouteComponent(
  () => import('@/features/tickets/sprints/SprintsView'),
  'SprintsView',
)
const BacklogView = lazyRouteComponent(
  () => import('@/features/tickets/sprints/BacklogView'),
  'BacklogView',
)
const SpaceSkillsView = lazyRouteComponent(
  () => import('@/features/skills/SpaceSkillsView'),
  'SpaceSkillsView',
)
const ProposalsView = lazyRouteComponent(
  () => import('@/features/proposals/ProposalsView'),
  'ProposalsView',
)
const ProposalScreen = lazyRouteComponent(
  () => import('@/features/proposals/ProposalScreen'),
  'ProposalScreen',
)
const SkillPage = lazyRouteComponent(() => import('@/features/skills/SkillPage'), 'SkillPage')

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
  validateSearch: boardSearch,
  component: function BoardRoute() {
    const search = boardRoute.useSearch()
    const navigate = boardRoute.useNavigate()
    return (
      <BoardView
        search={search}
        onSearch={(next) => void navigate({ search: next, replace: true })}
      />
    )
  },
})

const epicsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/epics',
  component: EpicsView,
})

/** A space's sprints and its backlog (tickets in no sprint), plan M4b. */
const sprintsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/sprints',
  component: SprintsView,
})

const backlogRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/backlog',
  component: BacklogView,
})

/** A space's proposals (page editors) and one proposal with its diff and decision. */
const proposalsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/proposals',
  component: ProposalsView,
})

const proposalRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/proposals/$proposalId',
  loader: () => ProposalScreen.preload?.(),
  component: function ProposalRoute() {
    const { proposalId } = proposalRoute.useParams()
    return <ProposalScreen proposalId={proposalId} />
  },
})

/** A space's skills (`ai.use` or `skill.manage`, and a role in the space). */
const skillsRoute = createRoute({
  getParentRoute: () => spaceRoute,
  path: '/skills',
  component: SpaceSkillsView,
})

/** One skill, wherever it belongs (the API answers 404 to whoever may not read it). */
export const skillRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/skills/$skillId',
  loader: () => SkillPage.preload?.(),
  component: function SkillRoute() {
    const { skillId } = skillRoute.useParams()
    return <SkillPage skillId={skillId} />
  },
})

export const spaceTree = spaceRoute.addChildren([
  spaceIndexRoute,
  pageRoute,
  trashRoute,
  spaceSettingsRoute,
  boardRoute,
  epicsRoute,
  sprintsRoute,
  backlogRoute,
  skillsRoute,
  proposalsRoute,
  proposalRoute,
])
