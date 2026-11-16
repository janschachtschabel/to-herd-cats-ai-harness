import { useNavigate, useSearch } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Field, SaveError } from '@/features/shared/forms'
import { OidcButtons } from './OidcButtons'
import { PendingApproval } from './PendingApproval'
import { SecondFactorForm } from './SecondFactorForm'
import { useLogin, useSignInProviders } from './queries'

/** A self-registered account that waits for approval: its own page, no form. */
const PENDING = 'oidc.account_pending'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { redirect, error, second_factor } = useSearch({ from: '/login' })
  const login = useLogin()
  const withProviders = useSignInProviders().length > 0
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // After a provider the address says so; after the password, the answer.
  const [waiting, setWaiting] = useState(second_factor === 'totp')
  const onward = () => void navigate({ to: redirect ?? '/spaces' })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    login.mutate(
      { email, password },
      { onSuccess: (result) => (result.signedIn ? onward() : setWaiting(true)) },
    )
  }

  function restart() {
    setWaiting(false)
    setPassword('')
    login.reset()
    void navigate({ to: '/login', search: { redirect }, replace: true })
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-muted p-4">
      <div className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        <span aria-hidden className="inline-block size-3 rounded-full bg-primary" />
        {t('app.name')}
      </div>
      {error === PENDING ? (
        <PendingApproval />
      ) : waiting ? (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>
              <h1 className="text-lg font-semibold">{t('totp.signIn.title')}</h1>
            </CardTitle>
            <CardDescription>{t('totp.signIn.hint')}</CardDescription>
          </CardHeader>
          <CardContent>
            <SecondFactorForm onSignedIn={onward} onRestart={restart} />
          </CardContent>
        </Card>
      ) : (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>
              <h1 className="text-lg font-semibold">{t('auth.title')}</h1>
            </CardTitle>
            <CardDescription>
              {withProviders ? t('signin.hintWithProviders') : t('auth.hint')}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <OidcButtons error={error} />
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
      )}
    </main>
  )
}
