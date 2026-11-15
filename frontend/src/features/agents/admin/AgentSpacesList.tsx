import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useAgentSpaces } from '../adminQueries'

/** The spaces the agent is a member of, with its role there. Members are added and
 *  removed in a space's settings, where each link leads. */
export function AgentSpacesList({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const spaces = useAgentSpaces(agentId)
  return (
    <section aria-labelledby="agent-spaces" className="flex flex-col gap-3 rounded-lg border p-4">
      <h2 id="agent-spaces" className="text-base font-semibold">
        {t('agents.spaces.title')}
      </h2>
      <p className="text-sm text-muted-foreground">{t('agents.spaces.hint')}</p>
      {spaces.isPending ? (
        <LoadingState rows={2} />
      ) : spaces.isError ? (
        <ErrorState error={spaces.error} onRetry={() => void spaces.refetch()} />
      ) : spaces.items.length === 0 ? (
        <EmptyState text={t('agents.spaces.empty')} />
      ) : (
        <ul aria-label={t('agents.spaces.listLabel')} className="divide-y text-sm">
          {spaces.items.map((space) => (
            <li key={space.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <Link
                to="/spaces/$spaceId/settings"
                params={{ spaceId: space.id }}
                className="font-medium underline-offset-4 hover:underline"
              >
                {space.name}
              </Link>
              <span className="flex gap-1">
                <Badge variant="outline">{t(`spaces.kinds.${space.kind}.label`)}</Badge>
                <Badge variant="secondary">{t(`roles.${space.role}`)}</Badge>
              </span>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={spaces.hasMore} loading={spaces.loadingMore} onLoad={spaces.loadMore} />
    </section>
  )
}
