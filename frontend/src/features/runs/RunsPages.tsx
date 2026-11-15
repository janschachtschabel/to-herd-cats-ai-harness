import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/features/shared/states'
import { useAgentRuns, useMyRuns, type RunFilters } from './queries'
import { RunFilterBar, RunList } from './RunList'

/** "Meine Läufe": the runs I asked for (a message, a mention, a ticket I assigned),
 *  newest first, filtered by state and stop reason. */
export function MyRunsPage({
  filters,
  onFilters,
}: {
  filters: RunFilters
  onFilters: (next: RunFilters) => void
}) {
  const { t } = useTranslation()
  const runs = useMyRuns(filters)
  return (
    <div>
      <PageHeader title={t('runs.mine.title')} description={t('runs.mine.description')} />
      <RunFilterBar filters={filters} onChange={onFilters} />
      <RunList list={runs} showAgent emptyText={t('runs.mine.empty')} />
    </div>
  )
}

/** Every run of one agent, for its responsible person, its owner and agent admins (the
 *  API answers 404 to everyone else, shown as not found). */
export function AgentRunsPage({
  agentId,
  filters,
  onFilters,
}: {
  agentId: string
  filters: RunFilters
  onFilters: (next: RunFilters) => void
}) {
  const { t } = useTranslation()
  const runs = useAgentRuns(agentId, filters)
  const name = runs.items[0]?.agent_name
  return (
    <div>
      <PageHeader
        title={name ? t('runs.agent.title', { name }) : t('runs.agent.titleUnnamed')}
        description={t('runs.agent.description')}
      />
      <RunFilterBar filters={filters} onChange={onFilters} />
      <RunList list={runs} showAgent={false} emptyText={t('runs.agent.empty')} />
    </div>
  )
}
