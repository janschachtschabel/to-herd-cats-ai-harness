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
import { QrCode } from './QrCode'
import { RecoveryCodes } from './RecoveryCodes'
import { useConfirmTotp, useStartTotp } from './queries'

/** The key in groups of four, easier to type into an app by hand. */
function grouped(secret: string): string {
  return secret.replace(/(.{4})(?=.)/g, '$1 ')
}

/** Setting TOTP up: the password, then the secret as a QR code and as text with the
 *  first code, then the recovery codes. The secret and the codes live only in this
 *  dialog's state and are gone when it closes. */
export function SetupDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('totp.setup.title')}</DialogTitle>
          <DialogDescription>{t('totp.profile.description')}</DialogDescription>
        </DialogHeader>
        {open && <SetupSteps onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function SetupSteps({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const start = useStartTotp()
  const confirm = useConfirmTotp()
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')

  if (confirm.data) {
    return (
      <div className="flex flex-col gap-4">
        <p role="status" className="text-sm">
          {t('totp.setup.done')}
        </p>
        <h3 className="text-sm font-medium">{t('totp.codes.title')}</h3>
        <RecoveryCodes codes={confirm.data} />
        <FormActions>
          <Button type="button" onClick={onClose}>
            {t('totp.codes.close')}
          </Button>
        </FormActions>
      </div>
    )
  }

  if (start.data) {
    const secret = start.data
    const onConfirm = (event: FormEvent) => {
      event.preventDefault()
      confirm.mutate(code.trim())
    }
    return (
      <form onSubmit={onConfirm} className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">{t('totp.setup.scan')}</p>
        <div className="flex flex-col items-center gap-3">
          <QrCode value={secret.uri} label={t('totp.setup.qr')} />
          <div className="text-center">
            <p className="text-xs text-muted-foreground">{t('totp.setup.secret')}</p>
            <p className="font-mono text-sm break-all select-all">{grouped(secret.secret)}</p>
          </div>
        </div>
        <Field label={t('totp.setup.code')} hint={t('totp.setup.codeHint')}>
          {(props) => (
            <Input
              {...props}
              required
              autoComplete="one-time-code"
              inputMode="numeric"
              className="w-40 font-mono tracking-widest"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          )}
        </Field>
        <SaveError error={confirm.error} />
        <FormActions>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('actions.cancel')}
          </Button>
          <Button type="submit" disabled={confirm.isPending}>
            {t('totp.setup.confirm')}
          </Button>
        </FormActions>
      </form>
    )
  }

  const onStart = (event: FormEvent) => {
    event.preventDefault()
    start.mutate(password)
  }
  return (
    <form onSubmit={onStart} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('totp.setup.passwordHint')}</p>
      <Field label={t('totp.setup.password')}>
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
      <SaveError error={start.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onClose}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={start.isPending}>
          {t('totp.setup.next')}
        </Button>
      </FormActions>
    </form>
  )
}
