import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { signInHref } from '@/features/auth/queries'
import { Field, FormActions, SaveError } from '@/features/shared/forms'

/** Before a new account is linked the person proves herself again (ASVS V7.5.1): her
 *  current password, or, without one, a fresh sign-in through a provider she already
 *  uses (`proofs`). */
export function ReauthDialog({
  open,
  providerName,
  proofs,
  pending,
  error,
  onSubmit,
  onOpenChange,
}: {
  open: boolean
  providerName: string
  proofs: { key: string; name: string }[]
  pending: boolean
  error: unknown
  onSubmit: (password: string) => void
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const [password, setPassword] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(password)
  }
  const change = (next: boolean) => {
    if (!next) setPassword('')
    onOpenChange(next)
  }
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('security.reauth.title')}</DialogTitle>
          <DialogDescription>{t('security.reauth.hint', { name: providerName })}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label={t('security.reauth.password')}>
            {(props) => (
              <Input
                {...props}
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <p className="text-sm text-muted-foreground">{t('security.reauth.noPassword')}</p>
          {proofs.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {proofs.map((proof) => (
                <Button key={proof.key} type="button" variant="outline" size="sm" asChild>
                  <a href={signInHref(proof.key, { reauth: true })}>
                    {t('security.reauth.viaProvider', { name: proof.name })}
                  </a>
                </Button>
              ))}
            </div>
          )}
          <SaveError error={error} />
          <FormActions>
            <Button type="button" variant="outline" onClick={() => change(false)}>
              {t('actions.cancel')}
            </Button>
            <Button type="submit" disabled={pending || password === ''}>
              {t('security.reauth.submit')}
            </Button>
          </FormActions>
        </form>
      </DialogContent>
    </Dialog>
  )
}
