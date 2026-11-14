import { createRoute, lazyRouteComponent, notFound } from '@tanstack/react-router'
import { hasPermission } from '@/features/auth/queries'
import type { RunFilters } from '@/features/runs/queries'
import type { Me } from '@/lib/api'
import { appRoute } from './base'

// Working with agents (plan M6 task 12): runs, the run page, an agent's runs, my
// releases. Every
// view is its own chunk, as in routes.tsx.
const MyRunsPage = lazyRouteComponent(() => import('@/features/runs/RunsPages'), 'MyRunsPage')
const AgentRunsPage = lazyRouteComponent(() => import('@/features/runs/RunsPages'), 'AgentRunsPage')
const RunScreen = lazyRouteComponent(() => import('@/features/runs/RunScreen'), 'RunScreen')
const ApprovalsPage = lazyRouteComponent(
  () => import('@/features/approvals/ApprovalsPage'),
  'ApprovalsPage',
)

const RUN_STATES = new Set(['queued', 'running', 'waiting', 'done'])
const STOP_REASONS = new Set([
  'completed',
  'max_steps',
  'deadline',
  'no_progress',
  'rights_revoked',
  'policy_blocked',
  'provider_refused',
  'error',
  'cancelled',
  'waiting_timeout',
  'approval_expired',
])

/** A run list's filters from the address; anything unknown is dropped. */
export function runSearch(search: Record<string, unknown>): RunFilters {
  const state = typeof search.state === 'string' && RUN_STATES.has(search.state)
  const reason = typeof search.stop_reason === 'string' && STOP_REASONS.has(search.stop_reason)
  return {
    ...(state ? { state: search.state as RunFilters['state'] } : {}),
    ...(reason ? { stop_reason: search.stop_reason as RunFilters['stop_reason'] } : {}),
  }
}

/** "My runs" are for people with AI or who manage agents (the API answers 404 else). */
function requireRuns(me: Me): void {
  if (!hasPermission(me, 'ai.use') && !hasPermission(me, 'agent.manage')) throw notFound()
}

const myRunsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/runs',
  validateSearch: runSearch,
  loader: ({ context }) => {
    requireRuns(context.me)
    return MyRunsPage.preload?.()
  },
  component: function MyRunsRoute() {
    const filters = myRunsRoute.useSearch()
    const navigate = myRunsRoute.useNavigate()
    return (
      <MyRunsPage
        filters={filters}
        onFilters={(next) => void navigate({ search: next, replace: true })}
      />
    )
  },
})

/** One run; whoever the API does not show it to gets its 404 in words. */
const runRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/runs/$runId',
  loader: () => RunScreen.preload?.(),
  component: function RunRoute() {
    const { runId } = runRoute.useParams()
    return <RunScreen runId={runId} />
  },
})

/** Every run of an agent (its responsible person, its owner, agent admins). */
const agentRunsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/agents/$agentId/runs',
  validateSearch: runSearch,
  loader: () => AgentRunsPage.preload?.(),
  component: function AgentRunsRoute() {
    const { agentId } = agentRunsRoute.useParams()
    const filters = agentRunsRoute.useSearch()
    const navigate = agentRunsRoute.useNavigate()
    return (
      <AgentRunsPage
        agentId={agentId}
        filters={filters}
        onFilters={(next) => void navigate({ search: next, replace: true })}
      />
    )
  },
})

/** The releases agents asked of me (people with AI; others are never asked). */
const approvalsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/approvals',
  loader: ({ context }) => {
    requireRuns(context.me)
    return ApprovalsPage.preload?.()
  },
  component: ApprovalsPage,
})

export const aiWorkRoutes = [myRunsRoute, runRoute, agentRunsRoute, approvalsRoute]
