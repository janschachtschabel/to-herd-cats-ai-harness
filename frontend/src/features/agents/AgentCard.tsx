import { Link, useNavigate } from '@tanstack/react-router'
import {
  Activity,
  Bot,
  MessageSquare,
  Pause,
  Pencil,
  Play,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { ExternalBadge } from './external/ExternalBadge'
import { useDeleteAgent, useOpenAgentDm, useUpdateAgent, type Agent } from './queries'

const STATUS_VARIANT = { active: 'secondary', paused: 'destructive', draft: 'outline' } as const

/** Talk to one's own agent: opens (or finds again) the direct message with it. */
function TalkButton({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const open = useOpenAgentDm()
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={open.isPending}
      onClick={() =>
        open.mutate(agentId, {
          onSuccess: (dm) =>
            void navigate({ to: '/c/$conversationId', params: { conversationId: dm.id } }),
        })
      }
    >
      <MessageSquare aria-hidden />
      {t('agents.personal.talk')}
    </Button>
  )
}

/** One agent: name, status, model, introduction; edit, pause or activate, delete. In
 *  the administration a personal agent is marked with its owner's name; on "my agents"
 *  (`mine`) the settings are the owner's page and one can talk to it. */
export function AgentCard({
  agent,
  connectionName,
  onEdit,
  mine = false,
}: {
  agent: Agent
  connectionName: string | null
  onEdit: () => void
  mine?: boolean
}) {
  const { t } = useTranslation()
  const update = useUpdateAgent(agent.id)
  const remove = useDeleteAgent()
  const [confirming, setConfirming] = useState(false)
  const next = agent.status === 'active' ? 'paused' : 'active'
  const external = agent.kind === 'external'

  return (
    <article aria-label={agent.name} className="flex h-full flex-col gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold break-words">
          <Bot className="size-4 text-muted-foreground" aria-hidden />
          {agent.name}
        </h2>
        <span className="flex flex-wrap gap-1">
          {agent.owner_user_id && !mine && (
            <Badge variant="outline">
              {t('agents.personal.owned', {
                name: agent.responsible_name ?? t('agents.personal.unknownOwner'),
              })}
            </Badge>
          )}
          {external && <ExternalBadge />}
          <Badge variant="outline">{t('agents.level.badge', { level: agent.level })}</Badge>
          <Badge variant={STATUS_VARIANT[agent.status]}>{t(`agents.status.${agent.status}`)}</Badge>
        </span>
      </div>
      {agent.intro && <p className="text-sm text-muted-foreground">{agent.intro}</p>}
      {!mine && !external && (
        <p className="text-xs text-muted-foreground">
          {t('agents.card.model', { model: agent.model, connection: connectionName ?? '–' })}
          {' · '}
          {t('agents.card.limits', { steps: agent.max_steps, seconds: agent.max_runtime_seconds })}
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
        {mine && agent.status === 'active' && <TalkButton agentId={agent.id} />}
        <Button size="sm" variant="outline" asChild>
          {mine ? (
            <Link to="/my-agents/$agentId" params={{ agentId: agent.id }}>
              <SlidersHorizontal aria-hidden />
              {t('agents.personal.settings')}
            </Link>
          ) : (
            <Link to="/admin/agents/$agentId" params={{ agentId: agent.id }}>
              <SlidersHorizontal aria-hidden />
              {external ? t('agents.external.open') : t('agents.admin.open')}
            </Link>
          )}
        </Button>
        {!external && (
          <Button size="sm" variant="outline" asChild>
            <Link to="/agents/$agentId/runs" params={{ agentId: agent.id }}>
              <Activity aria-hidden />
              {t('runs.agent.open')}
            </Link>
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          disabled={update.isPending}
          onClick={() => update.mutate({ status: next, version: agent.version })}
        >
          {next === 'paused' ? <Pause aria-hidden /> : <Play aria-hidden />}
          {next === 'paused' ? t('agents.pause') : t('agents.activate')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('agents.deleteNamed', { name: agent.name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      <SaveError error={update.error} />
      <ConfirmDialog
        open={confirming}
        title={t('agents.deleteTitle')}
        text={t('agents.deleteText', { name: agent.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() =>
          remove.mutate(
            { id: agent.id, version: agent.version },
            { onSuccess: () => setConfirming(false) },
          )
        }
      />
    </article>
  )
}
