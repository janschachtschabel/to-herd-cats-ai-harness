import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { useChangePassword } from './queries'

type Values = Schemas['PasswordChangeIn']
const schema = bodySchema('PasswordChangeIn')

/** The person's own password: the current one, then the new one. */
export function PasswordForm() {
  const { t } = useTranslation()
  const change = useChangePassword()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: '', new_password: '' },
  })
  const errors = form.formState.errors
  const onSubmit = form.handleSubmit((values) =>
    change.mutate(values, { onSuccess: () => form.reset() }),
  )

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-label={t('profile.password.title')}
      className="flex flex-col gap-4"
    >
      <h2 className="text-base font-medium">{t('profile.password.title')}</h2>
      <Field label={t('profile.password.current')} error={errors.current_password?.message}>
        {(props) => (
          <Input
            {...props}
            type="password"
            autoComplete="current-password"
            {...form.register('current_password')}
          />
        )}
      </Field>
      <Field
        label={t('profile.password.new')}
        hint={t('profile.password.hint')}
        error={errors.new_password?.message}
      >
        {(props) => (
          <Input
            {...props}
            type="password"
            autoComplete="new-password"
            {...form.register('new_password')}
          />
        )}
      </Field>
      <SaveError error={change.error} />
      {change.isSuccess && (
        <p role="status" className="text-sm text-muted-foreground">
          {t('profile.password.changed')}
        </p>
      )}
      <div>
        <Button type="submit" disabled={change.isPending}>
          {t('profile.password.submit')}
        </Button>
      </div>
    </form>
  )
}
