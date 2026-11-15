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
import { useCreateClient, useUpdateClient } from '../connectorQueries'
import type { OAuthClient } from '../display'
import { requiring } from '../required'
import {
  clientValues,
  createBody,
  fieldOf,
  missingSecret,
  newClientValues,
  updateBody,
  type ClientValues,
} from './clientForm'
import { ClientFields } from './ClientFields'

const createSchema = bodySchema('ClientCreate')
const updateSchema = bodySchema('ClientUpdate')

/** Register an OAuth app (no `client`; its fields can be read from a server's
 *  metadata) or change one. */
export function ClientDialog({
  open,
  client,
  onOpenChange,
}: {
  open: boolean
  client?: OAuthClient
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {client ? t('mcp.clients.edit.title') : t('mcp.clients.create.title')}
          </DialogTitle>
          <DialogDescription>{t('mcp.clients.create.description')}</DialogDescription>
        </DialogHeader>
        {open && <ClientForm client={client} onDone={done} />}
      </DialogContent>
    </Dialog>
  )
}

function ClientForm({ client, onDone }: { client?: OAuthClient; onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateClient()
  const update = useUpdateClient(client?.id ?? '')
  const toBody = (values: ClientValues) =>
    client ? updateBody(values, client.version) : createBody(values)
  const form = useForm<ClientValues>({
    resolver: requiring(
      bodyResolver(client ? updateSchema : createSchema, toBody, fieldOf),
      missingSecret,
    ),
    defaultValues: client ? clientValues(client) : newClientValues(),
  })
  const error = create.error ?? update.error
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        client
          ? update.mutate(updateBody(values, client.version), { onSuccess: onDone })
          : create.mutate(createBody(values), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ClientFields form={form} creating={!client} secretStored={client?.has_client_secret} />
      <SaveError error={error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending || update.isPending}>
          {client ? t('actions.save') : t('mcp.clients.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
