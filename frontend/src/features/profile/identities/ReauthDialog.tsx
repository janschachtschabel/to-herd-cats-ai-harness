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
import { Field, FormActions, SaveError } from '@/features/shared/forms'

/** Before a new account is linked the person proves herself again (ASVS V7.5.1): her
 *  current password, or, without one, a fresh sign-in through her provider. */
export function ReauthDialog({
  open,
  providerName,
  pending,
  error,
  onSubmit,
  onOpenChange,
}: {
  open: boolean
  providerName: string
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
