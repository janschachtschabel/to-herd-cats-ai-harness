import { createRoute, lazyRouteComponent, notFound, Outlet, redirect } from '@tanstack/react-router'
import { adminLinks } from '@/app/shell/nav'
import { hasPermission } from '@/features/auth/queries'
import type { Me, Permission } from '@/lib/api'
import { appRoute } from './base'
import { serverSearch, skillsSearch } from './search'

const UsersPage = lazyRouteComponent(() => import('@/features/admin/users/UsersPage'), 'UsersPage')
const GroupsPage = lazyRouteComponent(
  () => import('@/features/admin/groups/GroupsPage'),
  'GroupsPage',
)
const GroupPage = lazyRouteComponent(() => import('@/features/admin/groups/GroupPage'), 'GroupPage')
const TagsPage = lazyRouteComponent(() => import('@/features/admin/tags/TagsPage'), 'TagsPage')
const AuditPage = lazyRouteComponent(() => import('@/features/admin/audit/AuditPage'), 'AuditPage')
const DmInspectPage = lazyRouteComponent(
  () => import('@/features/admin/dm-inspect/DmInspectPage'),
  'DmInspectPage',
)
const ConnectionsPage = lazyRouteComponent(
  () => import('@/features/ai/connections/ConnectionsPage'),
  'ConnectionsPage',
)
const AssignmentsPage = lazyRouteComponent(
  () => import('@/features/ai/assignments/AssignmentsPage'),
  'AssignmentsPage',
)
const UsagePage = lazyRouteComponent(() => import('@/features/ai/usage/UsagePage'), 'UsagePage')
const BudgetsPage = lazyRouteComponent(
  () => import('@/features/ai/budgets/BudgetsPage'),
  'BudgetsPage',
)
const McpAdminPage = lazyRouteComponent(
  () => import('@/features/tokens/McpAdminPage'),
  'McpAdminPage',
)
const ServersPage = lazyRouteComponent(
  () => import('@/features/mcp/servers/ServersPage'),
  'ServersPage',
)
const ServerPage = lazyRouteComponent(
  () => import('@/features/mcp/servers/ServerPage'),
  'ServerPage',
)
const ConnectorsPage = lazyRouteComponent(
  () => import('@/features/mcp/connectors/ConnectorsPage'),
  'ConnectorsPage',
)
const CatalogPage = lazyRouteComponent(
  () => import('@/features/mcp/catalog/CatalogPage'),
  'CatalogPage',
)
const AgentsPage = lazyRouteComponent(() => import('@/features/agents/AgentsPage'), 'AgentsPage')
const AgentAdminPage = lazyRouteComponent(
  () => import('@/features/agents/admin/AgentAdminPage'),
  'AgentAdminPage',
)

const SkillsAdminPage = lazyRouteComponent(
  () => import('@/features/skills/SkillsAdminPage'),
  'SkillsAdminPage',
)

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

const aiRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: ConnectionsPage,
})

const aiAssignmentsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/assignments',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: AssignmentsPage,
})

const aiUsageRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/usage',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: UsagePage,
})

const aiBudgetsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/budgets',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: BudgetsPage,
})

/** MCP access (plan M8): the switch, the data location and every access token. */
const mcpAccessRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/mcp',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: McpAdminPage,
})

/** External MCP servers (plan M8): the list, and one server with its tools. */
const mcpServersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/mcp-servers',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: ServersPage,
})

const mcpServerRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/mcp-servers/$serverId',
  validateSearch: serverSearch,
  loader: async ({ context }) => {
    requirePermission(context.me, 'ai.manage')
    await ServerPage.preload?.()
  },
  component: function McpServerRoute() {
    const { serverId } = mcpServerRoute.useParams()
    const { read } = mcpServerRoute.useSearch()
    return <ServerPage serverId={serverId} read={read} />
  },
})

const mcpConnectorsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/connectors',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: ConnectorsPage,
})

const mcpCatalogRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/ai/catalog',
  loader: ({ context }) => requirePermission(context.me, 'ai.manage'),
  component: CatalogPage,
})

const agentsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/agents',
  loader: ({ context }) => requirePermission(context.me, 'agent.manage'),
  component: AgentsPage,
})

/** One agent: its level, tool grants, spaces and skills. */
const agentRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/agents/$agentId',
  loader: async ({ context }) => {
    requirePermission(context.me, 'agent.manage')
    await AgentAdminPage.preload?.()
  },
  component: function AgentRoute() {
    const { agentId } = agentRoute.useParams()
    return <AgentAdminPage agentId={agentId} />
  },
})

/** Every skill of the organisation (`skill.manage`); `?view=proposals`: the
 *  proposals for skills. */
const skillsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/skills',
  validateSearch: skillsSearch,
  loader: ({ context }) => requirePermission(context.me, 'skill.manage'),
  component: function SkillsRoute() {
    const { view } = skillsRoute.useSearch()
    return <SkillsAdminPage view={view ?? 'skills'} />
  },
})

/** The administration (`/admin/...`): each page only for those with its right. */
export const adminTree = adminRoute.addChildren([
  adminIndexRoute,
  usersRoute,
  groupsRoute,
  groupRoute,
  tagsRoute,
  auditRoute,
  dmInspectRoute,
  aiRoute,
  aiAssignmentsRoute,
  aiUsageRoute,
  aiBudgetsRoute,
  mcpAccessRoute,
  mcpServersRoute,
  mcpServerRoute,
  mcpConnectorsRoute,
  mcpCatalogRoute,
  agentsRoute,
  agentRoute,
  skillsRoute,
])
