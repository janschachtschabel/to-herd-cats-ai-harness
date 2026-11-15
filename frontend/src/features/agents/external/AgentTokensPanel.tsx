import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { CreateTokenDialog } from '@/features/tokens/CreateTokenDialog'
import { useAgentTokens, type CreatedToken } from '@/features/tokens/queries'
import { SecretDialog } from '@/features/tokens/SecretDialog'
import { TokenList } from '@/features/tokens/TokenList'
import { useAgentSpaces } from '../adminQueries'

/** An external agent's tokens (plan M8): what it works with from outside. Create (the
 *  clear text once, with the setup for Claude Code or Codex and a first task), revoke,
 *  and its calls: the agent's activity over `/mcp`. */
export function AgentTokensPanel({ agentId, name }: { agentId: string; name: string }) {
  const { t } = useTranslation()
  const tokens = useAgentTokens(agentId)
  const spaces = useAgentSpaces(agentId)
  const [creating, setCreating] = useState(false)
  const [shown, setShown] = useState<CreatedToken | null>(null)
  const names = new Map(spaces.items.map((space) => [space.id, space.name]))
  return (
    <section aria-labelledby="agent-tokens" className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="agent-tokens" className="text-base font-semibold">
            {t('agents.external.tokens.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('agents.external.tokens.hint')}</p>
        </div>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus aria-hidden />
          {t('tokens.create.open')}
        </Button>
      </div>
      <TokenList
        tokens={tokens}
        owner={{ kind: 'agent', agentId }}
        spaceNames={names}
        emptyText={t('agents.external.tokens.empty', { name })}
        label={t('agents.external.tokens.title')}
      />
      <CreateTokenDialog
        open={creating}
        agentId={agentId}
        spaces={spaces}
        onOpenChange={setCreating}
        onCreated={(token) => {
          setCreating(false)
          setShown(token)
        }}
      />
      <SecretDialog token={shown} forAgent onClose={() => setShown(null)} />
    </section>
  )
}
