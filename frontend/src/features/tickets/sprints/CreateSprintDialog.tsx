import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { useCreateSprint } from './queries'

type Values = Schemas['SprintCreate']
const schema = bodySchema('SprintCreate')
/** The days a sprint may use (the server refuses others, 422 `sprint.dates_invalid`). */
const DAYS = { min: '2000-01-01', max: '2100-12-31' }

/** A new sprint of the space, planned: name, goal, first and last day. */
export function CreateSprintDialog({
  spaceId,
  open,
  onOpenChange,
}: {
  spaceId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('tickets.sprints.form.title')}</DialogTitle>
          <DialogDescription>{t('tickets.sprints.form.description')}</DialogDescription>
        </DialogHeader>
        {open && <CreateSprintForm spaceId={spaceId} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function CreateSprintForm({ spaceId, onDone }: { spaceId: string; onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateSprint(spaceId)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', goal: '', starts_on: '', ends_on: '' },
  })
  const errors = form.formState.errors
  const onSubmit = form.handleSubmit((values) => create.mutate(values, { onSuccess: onDone }))
  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex flex-col gap-4"
      aria-label={t('tickets.sprints.form.title')}
    >
      <Field label={t('tickets.sprints.form.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('name')} />}
      </Field>
      <Field label={t('tickets.sprints.form.goal')} error={errors.goal?.message}>
        {(props) => <Textarea {...props} rows={2} {...form.register('goal')} />}
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('tickets.sprints.form.starts')} error={errors.starts_on?.message}>
          {(props) => <Input {...props} type="date" {...DAYS} {...form.register('starts_on')} />}
        </Field>
        <Field label={t('tickets.sprints.form.ends')} error={errors.ends_on?.message}>
          {(props) => <Input {...props} type="date" {...DAYS} {...form.register('ends_on')} />}
        </Field>
      </div>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('tickets.sprints.form.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
