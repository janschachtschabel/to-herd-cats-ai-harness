import { useTranslation } from 'react-i18next'
import { useMe } from '@/features/auth/queries'
import { usesAi } from '@/features/ai/display'
import { AgentBadge } from './AgentBadge'
import { useAgentProfile } from './queries'

/** In the header of a direct message with an agent: the AI mark, the agent's short
 *  introduction and, if it is paused, that it will not answer now. */
export function AgentHeaderNote({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const me = useMe()
  const profile = useAgentProfile(usesAi(me) ? agentId : null)
  return (
    <div className="mt-1 flex flex-col gap-1">
      <div>
        <AgentBadge />
      </div>
      {profile.data?.intro && <p className="text-sm text-muted-foreground">{profile.data.intro}</p>}
      {profile.data?.status === 'paused' && (
        <p className="text-sm text-amber-800 dark:text-amber-300">{t('agents.header.paused')}</p>
      )}
    </div>
  )
}
