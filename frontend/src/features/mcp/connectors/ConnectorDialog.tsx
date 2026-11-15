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
import { useCreateConnector, useUpdateConnector, type ConnectorScope } from '../connectorQueries'
import type { AuthKind, Connector } from '../display'
import { requiring } from '../required'
import {
  connectorValues,
  createBody,
  fieldOf,
  missingFields,
  newConnectorValues,
  updateBody,
  type ConnectorValues,
  type KeyMode,
} from './connectorForm'
import { ConnectorFields } from './ConnectorFields'
import { useConnect } from './useConnect'

const createSchema = bodySchema('ConnectorCreate')
const updateSchema = bodySchema('ConnectorUpdate')

const KINDS: Record<ConnectorScope, readonly AuthKind[]> = {
  shared: ['bearer', 'header', 'oauth'],
  personal: ['bearer', 'header'],
}
const KEY_MODES: Record<ConnectorScope, readonly KeyMode[]> = {
  shared: ['value', 'env'],
  personal: ['value'],
}

/** Make a connector (no `connector`) or change one: its name, kind and key (a new key
 *  replaces the stored one, which is never shown). A new OAuth connector is connected
 *  right away (the browser goes to the provider). `server`: one's own connector for
 *  this server (personal only), named after it. */
export function ConnectorDialog({
  open,
  scope,
  connector,
  server,
  onOpenChange,
}: {
  open: boolean
  scope: ConnectorScope
  connector?: Connector
  server?: { id: string; name: string }
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {connector
              ? t('mcp.connectors.edit.title')
              : server
                ? t('mcp.my.tokenTitle', { name: server.name })
                : t('mcp.connectors.create.title')}
          </DialogTitle>
          <DialogDescription>{t('mcp.connectors.secretNote')}</DialogDescription>
        </DialogHeader>
        {open &&
          (connector ? (
            <EditForm scope={scope} connector={connector} onDone={done} />
          ) : (
            <CreateForm scope={scope} server={server} onDone={done} />
          ))}
      </DialogContent>
    </Dialog>
  )
}

function CreateForm({
  scope,
  server,
  onDone,
}: {
  scope: ConnectorScope
  server?: { id: string; name: string }
  onDone: () => void
}) {
  const { t } = useTranslation()
  const create = useCreateConnector(scope)
  const oauth = useConnect(scope)
  const serverId = server?.id ?? null
  const toBody = (values: ConnectorValues) => createBody(values, serverId)
  const form = useForm<ConnectorValues>({
    resolver: requiring(bodyResolver(createSchema, toBody, fieldOf), (v) => missingFields(v, true)),
    defaultValues: newConnectorValues(server?.name ?? ''),
  })
  const isOAuth = form.watch('auth_kind') === 'oauth'
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        create.mutate(toBody(values), {
          onSuccess: (made) => (made.auth_kind === 'oauth' ? oauth.connect(made.id) : onDone()),
        }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ConnectorFields form={form} creating kinds={KINDS[scope]} keyModes={KEY_MODES[scope]} />
      <SaveError error={create.error ?? oauth.error} />
      {oauth.unsafe && (
        <p role="alert" className="text-sm text-destructive">
          {t('mcp.connectors.unsafeAddress')}
        </p>
      )}
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending || oauth.pending}>
          {isOAuth ? t('mcp.connectors.create.submitConnect') : t('mcp.connectors.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditForm({
  scope,
  connector,
  onDone,
}: {
  scope: ConnectorScope
  connector: Connector
  onDone: () => void
}) {
  const { t } = useTranslation()
  const update = useUpdateConnector(scope, connector.id)
  const toBody = (values: ConnectorValues) => updateBody(values, connector.version)
  const form = useForm<ConnectorValues>({
    resolver: requiring(bodyResolver(updateSchema, toBody, fieldOf), (v) =>
      missingFields(v, false),
    ),
    defaultValues: connectorValues(connector),
  })
  const kinds = KINDS[scope].filter((kind) => kind !== 'oauth')
  return (
    <form
      onSubmit={form.handleSubmit((values) => update.mutate(toBody(values), { onSuccess: onDone }))}
      noValidate
      className="flex flex-col gap-4"
    >
      <ConnectorFields
        form={form}
        kinds={kinds}
        keyModes={['keep', ...KEY_MODES[scope]]}
        keyStored={connector.has_secret}
      />
      <SaveError error={update.error} />
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
