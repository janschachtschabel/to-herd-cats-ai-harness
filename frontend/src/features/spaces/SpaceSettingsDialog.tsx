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
import type { Schemas, Space } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { spaceQuery, useUpdateSpace } from './queries'

type Values = Schemas['SpaceUpdateIn']
const schema = bodySchema('SpaceUpdateIn')

export function SpaceSettingsDialog({
  space,
  open,
  onOpenChange,
}: {
  space: Space
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('spaces.settings.title')}</DialogTitle>
        </DialogHeader>
        {open && <SpaceSettingsForm space={space} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

/** Saves against the version it was opened with; after a 409 the person reloads that
 *  version and saves again, their input kept as typed. */
export function SpaceSettingsForm({ space, onDone }: { space: Space; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateSpace(space.id)
  const [version, setVersion] = useState(space.version)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: space.name,
      description: space.description,
      icon: space.icon,
      version: space.version,
    },
  })
  const errors = form.formState.errors

  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...spaceQuery(space.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }

  const onSubmit = form.handleSubmit((values) =>
    update.mutate({ ...values, version }, { onSuccess: onDone }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <Field label={t('spaces.fields.name')} error={errors.name?.message}>
          {(props) => <Input {...props} {...form.register('name')} />}
        </Field>
        <Field label={t('spaces.fields.icon')} error={errors.icon?.message}>
          {(props) => <Input {...props} {...form.register('icon', { setValueAs: blankToNull })} />}
        </Field>
      </div>
      <Field label={t('spaces.fields.description')} error={errors.description?.message}>
        {(props) => (
          <Textarea
            {...props}
            rows={3}
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
