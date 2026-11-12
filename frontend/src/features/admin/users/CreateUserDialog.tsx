import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { useCreateUser } from './queries'
import { SYSTEM_ROLES, USER_LOCALES } from './roles'

type Values = Schemas['UserCreate']
const schema = bodySchema('UserCreate')

export function CreateUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('users.create.title')}</DialogTitle>
        </DialogHeader>
        {open && <CreateUserForm onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateUser()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: null, system_role: 'member', locale: 'de' },
  })
  const errors = form.formState.errors
  const onSubmit = form.handleSubmit((values) => create.mutate(values, { onSuccess: onDone }))

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field label={t('users.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('name')} />}
      </Field>
      <Field label={t('users.fields.email')} error={errors.email?.message}>
        {(props) => <Input {...props} type="email" {...form.register('email')} />}
      </Field>
      <Field
        label={t('users.fields.password')}
        hint={t('users.create.passwordHint')}
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
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('users.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
