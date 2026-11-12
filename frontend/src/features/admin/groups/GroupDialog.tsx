import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Group, Schemas } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { groupQuery, useCreateGroup, useUpdateGroup } from './queries'

const createSchema = bodySchema('GroupCreate')
const updateSchema = bodySchema('GroupUpdateIn')

/** Create a group (no `group`) or change one. */
export function GroupDialog({
  open,
  group,
  onOpenChange,
}: {
  open: boolean
  group?: Group
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{group ? t('groups.edit.title') : t('groups.create.title')}</DialogTitle>
        </DialogHeader>
        {open &&
          (group ? (
            <EditGroupForm group={group} onDone={done} />
          ) : (
            <CreateGroupForm onDone={done} />
          ))}
      </DialogContent>
    </Dialog>
  )
}

function CreateGroupForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateGroup()
  const form = useForm<Schemas['GroupCreate']>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: null },
  })
  const errors = form.formState.errors
  return (
    <form
      onSubmit={form.handleSubmit((values) => create.mutate(values, { onSuccess: onDone }))}
      noValidate
      className="flex flex-col gap-4"
    >
      <Field label={t('groups.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('name')} />}
      </Field>
      <Field label={t('groups.fields.description')} error={errors.description?.message}>
        {(props) => (
          <Textarea
            {...props}
            rows={2}
            {...form.register('description', { setValueAs: blankToNull })}
          />
        )}
      </Field>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('groups.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditGroupForm({ group, onDone }: { group: Group; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateGroup(group.id)
  const [version, setVersion] = useState(group.version)
  const form = useForm<Schemas['GroupUpdateIn']>({
    resolver: zodResolver(updateSchema),
    defaultValues: { name: group.name, description: group.description, version: group.version },
  })
  const errors = form.formState.errors

  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...groupQuery(group.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }

  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        update.mutate({ ...values, version }, { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <Field label={t('groups.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} {...form.register('name')} />}
      </Field>
      <Field label={t('groups.fields.description')} error={errors.description?.message}>
        {(props) => (
          <Textarea
            {...props}
            rows={2}
            {...form.register('description', { setValueAs: blankToNull })}
          />
        )}
      </Field>
      <SaveError error={update.error} onReload={() => void reload()} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={update.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
