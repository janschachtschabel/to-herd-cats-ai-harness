import { useQueryClient } from '@tanstack/react-query'
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
import { FormActions, SaveError } from '@/features/shared/forms'
import { bodyResolver } from '@/lib/formResolver'
import { bodySchema } from '@/lib/schemas'
import type { Connection } from '../display'
import { connectionQuery, useCreateConnection, useUpdateConnection } from '../queries'
import { ConnectionFields } from './ConnectionFields'
import {
  connectionValues,
  createBody,
  fieldOf,
  newConnectionValues,
  updateBody,
  type ConnectionValues,
} from './form'

const createSchema = bodySchema('ConnectionCreate')
const updateSchema = bodySchema('ConnectionUpdate')

/** Create a connection (no `connection`) or change one. */
export function ConnectionDialog({
  open,
  connection,
  onOpenChange,
}: {
  open: boolean
  connection?: Connection
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {connection ? t('ai.connections.edit.title') : t('ai.connections.create.title')}
          </DialogTitle>
          <DialogDescription>{t('ai.connections.secretNote')}</DialogDescription>
        </DialogHeader>
        {open &&
          (connection ? (
            <EditForm connection={connection} onDone={done} />
          ) : (
            <CreateForm onDone={done} />
          ))}
      </DialogContent>
    </Dialog>
  )
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateConnection()
  const form = useForm<ConnectionValues>({
    resolver: bodyResolver(createSchema, createBody, fieldOf),
    defaultValues: newConnectionValues(),
  })
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        create.mutate(createBody(values), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ConnectionFields form={form} creating />
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('ai.connections.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditForm({ connection, onDone }: { connection: Connection; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateConnection(connection.id)
  const [version, setVersion] = useState(connection.version)
  const form = useForm<ConnectionValues>({
    resolver: bodyResolver(updateSchema, (v: ConnectionValues) => updateBody(v, version), fieldOf),
    defaultValues: connectionValues(connection),
  })

  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...connectionQuery(connection.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }

  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        update.mutate(updateBody(values, version), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ConnectionFields form={form} secretSet={connection.secret.set} />
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
