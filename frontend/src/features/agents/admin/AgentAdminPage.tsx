import { useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentAutomationsPanel } from '@/features/automations/AutomationsPages'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { agentKeys } from '../keys'
import { useAgent, useAgentTools } from '../adminQueries'
import { AgentLevelForm } from './AgentLevelForm'
import { AgentSkillsPanel } from './AgentSkillsPanel'
import { AgentSpacesList } from './AgentSpacesList'
import { AgentToolsForm } from './AgentToolsForm'
import { AgentTokensPanel } from '../external/AgentTokensPanel'
import { ExternalAgentTools } from '../external/ExternalAgentTools'
import { ExternalBadge } from '../external/ExternalBadge'

/** One agent for its managers (`agent.manage`): its autonomy level, the grant of each
 *  tool, the spaces it works in, its skills and its automations. An external agent
 *  (plan M8) has no skills, runs or automations here: its page shows the tools its
 *  tokens can reach, its tokens and its spaces. */
export function AgentAdminPage({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const agent = useAgent(agentId)
  const tools = useAgentTools(agentId)
  const reload = () => void queryClient.invalidateQueries({ queryKey: agentKeys.detail(agentId) })

  if (agent.isPending) return <LoadingState />
  if (agent.isError) return <ErrorState error={agent.error} onRetry={() => void agent.refetch()} />
  const external = agent.data.kind === 'external'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={agent.data.name}
        description={agent.data.intro || undefined}
        actions={
          <Button variant="outline" asChild>
            <Link to="/admin/agents">
              <ArrowLeft aria-hidden />
              {t('agents.admin.back')}
            </Link>
          </Button>
        }
      >
        <div className="mt-2 flex flex-wrap gap-2">
          {external && <ExternalBadge />}
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
            withheldNote={external ? t('agents.external.levelNote') : undefined}
            explainKey={external ? 'agents.external.levels' : undefined}
          />
          {external ? (
            <ExternalAgentTools shown={tools.data} onReload={reload} />
          ) : (
            <AgentToolsForm shown={tools.data} onReload={reload} />
          )}
        </>
      )}
      {external ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <AgentTokensPanel agentId={agentId} name={agent.data.name} />
          <AgentSpacesList agentId={agentId} />
        </div>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <AgentSpacesList agentId={agentId} />
            <AgentSkillsPanel agentId={agentId} onReload={reload} />
          </div>
          <AgentAutomationsPanel agentId={agentId} />
        </>
      )}
    </div>
  )
}
