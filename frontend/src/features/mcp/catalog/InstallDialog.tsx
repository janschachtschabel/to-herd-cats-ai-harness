import { useNavigate } from '@tanstack/react-router'
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
import { useInstallEntry } from '../catalogQueries'
import type { CatalogEntry } from '../display'
import { requiring } from '../required'
import { InstallFields } from './InstallFields'
import {
  fieldOf,
  installBody,
  installValues,
  missingInstall,
  type InstallValues,
} from './installForm'

const schema = bodySchema('InstallIn')

/** Install a template: the server (its tools read at once, every one pending), and
 *  what its access needs. Afterwards the server's page opens, to connect and approve. */
export function InstallDialog({
  entry,
  onOpenChange,
}: {
  entry: CatalogEntry | null
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={entry !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('mcp.catalog.install.title', { name: entry?.name ?? '' })}</DialogTitle>
          <DialogDescription>{t('mcp.catalog.install.description')}</DialogDescription>
        </DialogHeader>
        {entry && <InstallForm key={entry.id} entry={entry} onCancel={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function InstallForm({ entry, onCancel }: { entry: CatalogEntry; onCancel: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const install = useInstallEntry(entry.id)
  const toBody = (values: InstallValues) => installBody(entry, values)
  const form = useForm<InstallValues>({
    resolver: requiring(bodyResolver(schema, toBody, fieldOf), missingInstall),
    defaultValues: installValues(entry),
  })
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        install.mutate(toBody(values), {
          onSuccess: ({ server }) =>
            void navigate({
              to: '/admin/ai/mcp-servers/$serverId',
              params: { serverId: server.id },
              search: { read: server.refresh.status },
            }),
        }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <InstallFields entry={entry} form={form} />
      <SaveError error={install.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={install.isPending}>
          {install.isPending ? t('mcp.servers.create.reading') : t('mcp.catalog.install.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
