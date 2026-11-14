import { useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Activity, ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { AgentLevelForm } from '../admin/AgentLevelForm'
import { AgentSpacesList } from '../admin/AgentSpacesList'
import { AgentToolsForm } from '../admin/AgentToolsForm'
import { useAgent, useAgentTools } from '../adminQueries'
import { agentKeys } from '../keys'

/** One of my agents: its level (the API caps it: personal agents at most 2), the
 *  grant of each tool, where it works (my personal space), and its runs. */
export function PersonalAgentPage({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const agent = useAgent(agentId)
  const tools = useAgentTools(agentId)
  const reload = () => void queryClient.invalidateQueries({ queryKey: agentKeys.detail(agentId) })
  if (agent.isPending) return <LoadingState />
  if (agent.isError) return <ErrorState error={agent.error} onRetry={() => void agent.refetch()} />
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={agent.data.name}
        description={agent.data.intro || undefined}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/agents/$agentId/runs" params={{ agentId }}>
                <Activity aria-hidden />
                {t('runs.agent.open')}
              </Link>
            </Button>
            <Button variant="ghost" asChild>
              <Link to="/my-agents">
                <ArrowLeft aria-hidden />
                {t('agents.personal.back')}
              </Link>
            </Button>
          </>
        }
      >
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge variant="secondary">{t(`agents.status.${agent.data.status}`)}</Badge>
          <Badge variant="outline">{t('agents.level.badge', { level: agent.data.level })}</Badge>
        </div>
      </PageHeader>
      {tools.isPending ? (
        <LoadingState />
      ) : tools.isError ? (
        <ErrorState error={tools.error} onRetry={() => void tools.refetch()} />
      ) : (
        <>
          <AgentLevelForm
            agentId={agentId}
            level={tools.data.level}
            maxLevel={tools.data.max_level}
            version={tools.data.version}
            onReload={reload}
            withheldNote={t('agents.personal.levelCap')}
          />
          <AgentToolsForm shown={tools.data} onReload={reload} />
        </>
      )}
      <AgentSpacesList agentId={agentId} />
    </div>
  )
}
