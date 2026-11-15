import { useNavigate } from '@tanstack/react-router'
import { Pause, Play, Trash2, UserCheck, Zap } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { outcomeText } from './display'
import {
  useControlAutomation,
  useDeleteAutomation,
  useReloadAutomation,
  useRunAutomation,
  type Automation,
} from './queries'

/** What the reader may do with it, exactly as its `abilities` say (the API decides):
 *  pause, resume, take over (after a confirmation that says what it means), run now
 *  (how the term went is said), delete (after a confirmation). A stale version offers
 *  to load the current one; a refused resume says why. `edit` is the caller's button. */
export function AutomationActions({
  automation,
  edit,
}: {
  automation: Automation
  edit?: ReactNode
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const control = useControlAutomation(automation.id)
  const run = useRunAutomation(automation.id)
  const remove = useDeleteAutomation(automation.id)
  const reload = useReloadAutomation(automation.id)
  const [confirm, setConfirm] = useState<'delete' | 'take-over' | null>(null)
  const abilities = automation.abilities
  const version = automation.version
  const failed = confirm ? null : (control.error ?? run.error)

  const act = (action: 'pause' | 'resume') => {
    run.reset()
    control.mutate({ action, version })
  }
  const runNow = () => {
    control.reset()
    run.mutate()
  }
  const reloaded = async () => {
    await reload()
    control.reset()
    run.reset()
  }
  const ran = run.data?.last_run

  return (
    <div className="flex flex-col gap-3">
      <div
        role="group"
        aria-label={t('automations.actions.label')}
        className="flex flex-wrap gap-2"
      >
        {edit}
        {abilities.pause && (
          <Button variant="outline" onClick={() => act('pause')} disabled={control.isPending}>
            <Pause aria-hidden />
            {t('automations.actions.pause')}
          </Button>
        )}
        {abilities.resume && (
          <Button variant="outline" onClick={() => act('resume')} disabled={control.isPending}>
            <Play aria-hidden />
            {t('automations.actions.resume')}
          </Button>
        )}
        {abilities.take_over && (
          <Button variant="outline" onClick={() => setConfirm('take-over')}>
            <UserCheck aria-hidden />
            {t('automations.actions.takeOver')}
          </Button>
        )}
        {abilities.run && (
          <Button variant="outline" onClick={runNow} disabled={run.isPending}>
            <Zap aria-hidden />
            {t('automations.actions.run')}
          </Button>
        )}
        {abilities.delete && (
          <Button variant="outline" onClick={() => setConfirm('delete')}>
            <Trash2 aria-hidden />
            {t('automations.actions.delete')}
          </Button>
        )}
      </div>
      <p role="status" className="text-sm empty:hidden">
        {ran && run.isSuccess ? t('automations.actions.ran', { outcome: outcomeText(t, ran) }) : ''}
      </p>
      <SaveError error={failed} onReload={() => void reloaded()} />
      <ConfirmDialog
        open={confirm === 'take-over'}
        title={t('automations.takeOver.title')}
        text={t('automations.takeOver.text')}
        confirmLabel={t('automations.takeOver.confirm')}
        pending={control.isPending}
        error={control.error}
        onConfirm={() =>
          control.mutate({ action: 'take-over', version }, { onSuccess: () => setConfirm(null) })
        }
        onOpenChange={(open) => {
          setConfirm(open ? 'take-over' : null)
          if (!open) control.reset()
        }}
      />
      <ConfirmDialog
        open={confirm === 'delete'}
        title={t('automations.delete.title')}
        text={t('automations.delete.text')}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(version, {
            onSuccess: () => {
              setConfirm(null)
              void navigate({ to: '/automations' })
            },
          })
        }
        onOpenChange={(open) => {
          setConfirm(open ? 'delete' : null)
          if (!open) remove.reset()
        }}
      />
    </div>
  )
}
