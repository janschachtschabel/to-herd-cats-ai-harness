import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Page, Schemas, User } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { usersQuery, useUpdateUser } from './queries'
import { SYSTEM_ROLES, USER_LOCALES } from './roles'

type Values = Schemas['UserUpdateIn']
const schema = bodySchema('UserUpdateIn')

export function EditUserDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <Dialog open={user !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('users.edit.title', { name: user?.name ?? '' })}</DialogTitle>
        </DialogHeader>
        {user && <EditUserForm user={user} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  )
}

function EditUserForm({ user, onDone }: { user: User; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateUser(user.id)
  const [version, setVersion] = useState(user.version)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: user.name,
      system_role: user.system_role,
      locale: user.locale,
      password: null,
      version: user.version,
    },
  })
  const errors = form.formState.errors

  // There is no single-person endpoint: reload the list and take this person's version.
  const reload = async () => {
    await queryClient.refetchQueries({ queryKey: usersQuery.queryKey })
    const data = queryClient.getQueryData<InfiniteData<Page<User>>>(usersQuery.queryKey)
    const fresh = data?.pages.flatMap((page) => page.items).find((u) => u.id === user.id)
    if (fresh) setVersion(fresh.version)
    update.reset()
  }

  const onSubmit = form.handleSubmit((values) =>
    update.mutate({ ...values, version }, { onSuccess: onDone }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field label={t('users.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} {...form.register('name')} />}
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('users.fields.role')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('system_role')}>
              {SYSTEM_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`systemRoles.${role}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('users.fields.locale')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('locale')}>
              {USER_LOCALES.map((locale) => (
                <option key={locale} value={locale}>
                  {t(`userMenu.locales.${locale}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      <Field
        label={t('users.fields.newPassword')}
        hint={t('users.edit.passwordHint')}
        error={errors.password?.message}
      >
        {(props) => (
          <Input
            {...props}
            type="password"
            autoComplete="new-password"
            {...form.register('password', { setValueAs: blankToNull })}
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
