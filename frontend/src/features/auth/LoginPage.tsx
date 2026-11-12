import { useNavigate, useSearch } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Field, SaveError } from '@/features/shared/forms'
import { useLogin } from './queries'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { redirect } = useSearch({ from: '/login' })
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    login.mutate(
      { email, password },
      { onSuccess: () => void navigate({ to: redirect ?? '/spaces' }) },
    )
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-muted p-4">
      <div className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        <span aria-hidden className="inline-block size-3 rounded-full bg-primary" />
        {t('app.name')}
      </div>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1 className="text-lg font-semibold">{t('auth.title')}</h1>
          </CardTitle>
          <CardDescription>{t('auth.hint')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <Field label={t('auth.email')}>
              {(props) => (
                <Input
                  {...props}
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              )}
            </Field>
            <Field label={t('auth.password')}>
              {(props) => (
                <Input
                  {...props}
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Field>
            <SaveError error={login.error} />
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? t('auth.submitting') : t('auth.submit')}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
