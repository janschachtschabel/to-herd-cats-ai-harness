import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
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
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas, Space, Ticket } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { KINDS, PRIORITIES, type TicketKind } from './display'
import { useCreateTicket } from './queries'

type Values = Schemas['TicketCreate']
const schema = bodySchema('TicketCreate')

/** A new ticket in one of `spaces` (those where one may create tickets); with one
 *  space there is nothing to choose. `statusId` starts it in that status (a board
 *  column); without, the space's first open status. Opens the ticket afterwards
 *  unless `onCreated` says otherwise. */
export function CreateTicketDialog({
  open,
  onOpenChange,
  spaces,
  statusId,
  kind = 'task',
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  spaces: Space[]
  statusId?: string
  /** The kind to start with (an epic from the epic overview). */
  kind?: TicketKind
  onCreated?: (ticket: Ticket) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('tickets.create.title')}</DialogTitle>
          <DialogDescription>{t('tickets.create.description')}</DialogDescription>
        </DialogHeader>
        {open && spaces[0] && (
          <CreateTicketForm
            spaces={spaces}
            statusId={statusId}
            kind={kind}
            onCreated={onCreated}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function CreateTicketForm({
  spaces,
  statusId,
  kind,
  onCreated,
  onDone,
}: {
  spaces: Space[]
  statusId?: string
  kind: TicketKind
  onCreated?: (ticket: Ticket) => void
  onDone: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [spaceId, setSpaceId] = useState(spaces[0]!.id)
  const create = useCreateTicket(spaceId)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: '',
      kind,
      priority: 'normal',
      due_on: null,
      description_md: '',
    },
  })
  const errors = form.formState.errors

  const onSubmit = form.handleSubmit((values) =>
    create.mutate(
      { ...values, status_id: statusId ?? null },
      {
        onSuccess: (ticket) => {
          onDone()
          if (onCreated) onCreated(ticket)
          else void navigate({ to: '/tickets/$number', params: { number: String(ticket.number) } })
        },
      },
    ),
  )

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex flex-col gap-4"
      aria-label={t('tickets.create.title')}
    >
      {spaces.length > 1 && (
        <Field label={t('tickets.fields.space')}>
          {(props) => (
            <NativeSelect {...props} value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      <Field label={t('tickets.fields.title')} error={errors.title?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('title')} />}
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t('tickets.fields.kind')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('kind')}>
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`tickets.kinds.${kind}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('tickets.fields.priority')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('priority')}>
              {PRIORITIES.map((priority) => (
                <option key={priority} value={priority}>
                  {t(`tickets.priorities.${priority}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('tickets.fields.due')} error={errors.due_on?.message}>
          {(props) => (
            <Input
              {...props}
              type="date"
              {...form.register('due_on', { setValueAs: blankToNull })}
            />
          )}
        </Field>
      </div>
      <Field
        label={t('tickets.fields.description')}
        hint={t('tickets.fields.markdownHint')}
        error={errors.description_md?.message}
      >
        {(props) => <Textarea {...props} rows={5} {...form.register('description_md')} />}
      </Field>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('tickets.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
