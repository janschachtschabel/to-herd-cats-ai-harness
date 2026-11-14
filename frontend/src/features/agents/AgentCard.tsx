import { Bot, Pause, Pencil, Play, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { useDeleteAgent, useUpdateAgent, type Agent } from './queries'

const STATUS_VARIANT = { active: 'secondary', paused: 'destructive', draft: 'outline' } as const

/** One agent: name, status, model, introduction; edit, pause or activate, delete. */
export function AgentCard({
  agent,
  connectionName,
  onEdit,
}: {
  agent: Agent
  connectionName: string | null
  onEdit: () => void
}) {
  const { t } = useTranslation()
  const update = useUpdateAgent(agent.id)
  const remove = useDeleteAgent()
  const [confirming, setConfirming] = useState(false)
  const next = agent.status === 'active' ? 'paused' : 'active'

  return (
    <article aria-label={agent.name} className="flex h-full flex-col gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold break-words">
          <Bot className="size-4 text-muted-foreground" aria-hidden />
          {agent.name}
        </h2>
        <Badge variant={STATUS_VARIANT[agent.status]}>{t(`agents.status.${agent.status}`)}</Badge>
      </div>
      {agent.intro && <p className="text-sm text-muted-foreground">{agent.intro}</p>}
      <p className="text-xs text-muted-foreground">
        {t('agents.card.model', { model: agent.model, connection: connectionName ?? '–' })}
        {' · '}
        {t('agents.card.limits', { steps: agent.max_steps, seconds: agent.max_runtime_seconds })}
      </p>
      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
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
