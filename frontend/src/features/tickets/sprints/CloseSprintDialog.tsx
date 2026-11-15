import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SaveError } from '@/features/shared/forms'
import type { Schemas, Sprint } from '@/lib/api'
import { useCloseSprint } from './queries'
import { nextPlanned } from './rules'

/** Closes the running sprint after asking where its unfinished tickets go: into the
 *  next planned sprint (the one that starts first) or back into the backlog. */
export function CloseSprintDialog({
  sprint,
  sprints,
  open,
  onOpenChange,
}: {
  sprint: Sprint
  sprints: Sprint[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const next = nextPlanned(sprints)
  const close = useCloseSprint(sprint)
  const [choice, setChoice] = useState<Schemas['MoveOpenTo'] | null>(null)
  const target = choice ?? (next ? 'next' : 'backlog')
  const option = (value: Schemas['MoveOpenTo'], label: string, disabled = false) => (
    <label className="flex items-center gap-2 text-sm has-disabled:text-muted-foreground">
      <input
        type="radio"
        name="move-open-to"
        className="accent-primary"
        value={value}
        checked={target === value}
        disabled={disabled}
        onChange={() => setChoice(value)}
      />
      {label}
    </label>
  )
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) close.reset()
        onOpenChange(value)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('tickets.sprints.closeDialog.title', { name: sprint.name })}</DialogTitle>
          <DialogDescription>{t('tickets.sprints.closeDialog.text')}</DialogDescription>
        </DialogHeader>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">
            {t('tickets.sprints.closeDialog.legend')}
          </legend>
          {option(
            'next',
            next
              ? t('tickets.sprints.closeDialog.next', { name: next.name })
              : t('tickets.sprints.closeDialog.nextMissing'),
            !next,
          )}
          {option('backlog', t('tickets.sprints.closeDialog.backlog'))}
        </fieldset>
        <SaveError error={close.error} />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('actions.cancel')}
          </Button>
          <Button
            disabled={close.isPending}
            onClick={() => close.mutate(target, { onSuccess: () => onOpenChange(false) })}
          >
            {t('tickets.sprints.closeDialog.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
