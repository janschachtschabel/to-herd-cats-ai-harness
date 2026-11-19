import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, SaveError } from '@/features/shared/forms'
import { ApiError } from '@/lib/api'
import { useSecondFactor } from './queries'

/** A waiting sign-in that is over (expired, used up, too many wrong codes): only the
 *  first step helps. */
const EXPIRED = 'auth.second_factor_expired'

/** The second step of a sign-in: a code from the authenticator app, or one of the
 *  recovery codes. `onSignedIn` once the session is open; `onRestart` back to the
 *  first step. */
export function SecondFactorForm({
  onSignedIn,
  onRestart,
}: {
  onSignedIn: () => void
  onRestart: () => void
}) {
  const { t } = useTranslation()
  const finish = useSecondFactor()
  const [recovery, setRecovery] = useState(false)
  const [value, setValue] = useState('')
  const expired = finish.error instanceof ApiError && finish.error.code === EXPIRED

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const body = recovery ? { recovery_code: value.trim() } : { code: value.trim() }
    finish.mutate(body, { onSuccess: onSignedIn })
  }

  function toggle() {
    setRecovery(!recovery)
    setValue('')
    finish.reset()
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <Field
        label={recovery ? t('totp.signIn.recoveryCode') : t('totp.signIn.code')}
        hint={recovery ? t('totp.signIn.recoveryHint') : t('totp.signIn.codeHint')}
      >
        {(props) => (
          <Input
            {...props}
            autoFocus
            required
            autoComplete={recovery ? 'off' : 'one-time-code'}
            inputMode={recovery ? 'text' : 'numeric'}
            spellCheck={false}
            className={recovery ? 'font-mono uppercase' : 'font-mono tracking-widest'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        )}
      </Field>
      <SaveError error={finish.error} />
      {expired ? (
        <Button type="button" onClick={onRestart}>
          {t('totp.signIn.restart')}
        </Button>
      ) : (
        <Button type="submit" disabled={finish.isPending}>
          {finish.isPending ? t('totp.signIn.submitting') : t('totp.signIn.submit')}
        </Button>
      )}
      <div className="flex flex-wrap justify-between gap-2">
        <Button type="button" variant="link" className="h-auto px-0" onClick={toggle}>
          {recovery ? t('totp.signIn.useCode') : t('totp.signIn.useRecovery')}
        </Button>
        {!expired && (
          <Button type="button" variant="link" className="h-auto px-0" onClick={onRestart}>
            {t('totp.signIn.restart')}
          </Button>
        )}
      </div>
    </form>
  )
}
