import { createRoute, lazyRouteComponent, notFound } from '@tanstack/react-router'
import { hasPermission } from '@/features/auth/queries'
import { appRoute } from './base'

// Access tokens for AI clients over MCP (plan M8): one's own, under the personal
// settings. Its own chunk, as every page.
const MyTokensPage = lazyRouteComponent(
  () => import('@/features/tokens/MyTokensPage'),
  'MyTokensPage',
)

/** My access tokens: only with `mcp.use` (the API answers 404 to everyone else). */
const myTokensRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/profile/tokens',
  loader: ({ context }) => {
    if (!hasPermission(context.me, 'mcp.use')) throw notFound()
    return MyTokensPage.preload?.()
  },
  component: MyTokensPage,
})

export const tokenRoutes = [myTokensRoute]
