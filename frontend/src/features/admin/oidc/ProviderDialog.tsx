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
import { Callback } from './Callback'
import { ProviderFields } from './ProviderFields'
import {
  createBody,
  newProviderValues,
  providerResolver,
  providerValues,
  updateBody,
  type ProviderKind,
  type ProviderValues,
} from './providerForm'
import {
  oidcProviderQuery,
  useCreateOidcProvider,
  useUpdateOidcProvider,
  type OidcProvider,
} from './queries'

/** Set up a provider of `kind` (no `provider`) or change one. */
export function ProviderDialog({
  open,
  kind,
  provider,
  onOpenChange,
}: {
  open: boolean
  kind?: ProviderKind
  provider?: OidcProvider
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  const shownKind = provider?.kind ?? kind ?? 'google'
  const title = provider
    ? t('oidcAdmin.form.edit')
    : shownKind === 'google'
      ? t('oidcAdmin.form.createGoogle')
      : t('oidcAdmin.form.createGeneric')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {provider
              ? t('oidcAdmin.form.editHint')
              : shownKind === 'google'
                ? t('oidcAdmin.form.googleHint')
                : t('oidcAdmin.form.genericHint')}
          </DialogDescription>
        </DialogHeader>
        {open &&
          (provider ? (
            <EditForm provider={provider} onDone={done} />
          ) : (
            <CreateForm kind={shownKind} onDone={done} />
          ))}
      </DialogContent>
    </Dialog>
  )
}

function CreateForm({ kind, onDone }: { kind: ProviderKind; onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateOidcProvider()
  const form = useForm<ProviderValues>({
    resolver: providerResolver(undefined),
    defaultValues: newProviderValues(kind),
  })
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        create.mutate(createBody(values), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <ProviderFields form={form} creating />
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('oidcAdmin.form.submitCreate')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditForm({ provider, onDone }: { provider: OidcProvider; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateOidcProvider(provider.id)
  const [current, setCurrent] = useState(provider)
  const form = useForm<ProviderValues>({
    resolver: providerResolver(current),
    defaultValues: providerValues(provider),
  })

  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...oidcProviderQuery(provider.id), staleTime: 0 })
    setCurrent(fresh)
    update.reset()
  }

  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        update.mutate(updateBody(values, current.version), { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">{t('oidcAdmin.callback')}</span>
        <Callback url={current.callback_url} />
      </div>
      <ProviderFields form={form} secretSet={current.client_secret.set} />
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
