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
import type { CreatedServer, Server } from '../display'
import { requiring } from '../required'
import { serverQuery, useCreateServer, useUpdateServer } from '../serverQueries'
import { ServerFields } from './ServerFields'
import {
  createBody,
  newServerValues,
  serverValues,
  updateBody,
  urlChanged,
  type ServerValues,
} from './serverForm'

const createSchema = bodySchema('ServerCreate')
const updateSchema = bodySchema('ServerUpdate')

/** The body's schema, plus: a shared access needs its connector. */
function serverResolver(toBody: (values: ServerValues) => unknown, create: boolean) {
  return requiring(bodyResolver(create ? createSchema : updateSchema, toBody), (values) =>
    values.connector_scope === 'shared' && values.connector_id === '' ? ['connector_id'] : [],
  )
}

/** Add a server by its address (no `server`), or change one. */
export function ServerDialog({
  open,
  server,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  server?: Server
  onOpenChange: (open: boolean) => void
  onCreated?: (server: CreatedServer) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {server ? t('mcp.servers.edit.title') : t('mcp.servers.create.title')}
          </DialogTitle>
          <DialogDescription>{t('mcp.servers.create.description')}</DialogDescription>
        </DialogHeader>
        {open &&
          (server ? (
            <EditForm server={server} onDone={done} />
          ) : (
            <CreateForm
              onDone={(created) => {
                done()
                onCreated?.(created)
              }}
              onCancel={done}
            />
          ))}
      </DialogContent>
    </Dialog>
  )
}

function CreateForm({
  onDone,
  onCancel,
}: {
  onDone: (server: CreatedServer) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const create = useCreateServer()
  const form = useForm<ServerValues>({
    resolver: serverResolver(createBody, true),
    defaultValues: newServerValues(),
  })
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        create.mutate(createBody(values), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ServerFields form={form} creating />
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? t('mcp.servers.create.reading') : t('mcp.servers.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditForm({ server, onDone }: { server: Server; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateServer(server.id)
  const [version, setVersion] = useState(server.version)
  const form = useForm<ServerValues>({
    resolver: serverResolver((v) => updateBody(v, version), false),
    defaultValues: serverValues(server),
  })
  const moved = urlChanged(server, form.watch())

  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...serverQuery(server.id), staleTime: 0 })
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
      <ServerFields form={form} />
      {moved && (
        <p role="note" className="text-sm text-amber-800 dark:text-amber-300">
          {t('mcp.servers.urlWithdraws')}
        </p>
      )}
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
