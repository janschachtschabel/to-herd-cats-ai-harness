import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { FormActions } from '@/features/shared/forms'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { CodeDialog } from './CodeDialog'
import { RecoveryCodes } from './RecoveryCodes'
import { SetupDialog } from './SetupDialog'
import { proofOf, useDisableTotp, useRenewRecoveryCodes, useTotpStatus } from './queries'

type Open = 'setup' | 'disable' | 'renew' | null

/** The person's own second factor: set up, turn off, new recovery codes. */
export function TotpSection() {
  const { t, i18n } = useTranslation()
  const status = useTotpStatus()
  const disable = useDisableTotp()
  const renew = useRenewRecoveryCodes()
  const [open, setOpen] = useState<Open>(null)
  const close = () => {
    setOpen(null)
    disable.reset()
    renew.reset()
  }
  const data = status.data
  return (
    <section className="mt-8 flex flex-col gap-3 border-t pt-6" aria-labelledby="totp-title">
      <div>
        <h2 id="totp-title" className="text-base font-semibold">
          {t('totp.profile.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('totp.profile.description')}</p>
      </div>
      {status.isPending ? (
        <LoadingState />
      ) : status.isError || !data ? (
        <ErrorState error={status.error} onRetry={() => void status.refetch()} />
      ) : data.enabled_at ? (
        <>
          <div className="text-sm">
            <p>{t('totp.profile.on', { date: formatDateTime(data.enabled_at, i18n.language) })}</p>
            <p className="text-muted-foreground">
              {t('totp.profile.codesLeft', { count: data.recovery_codes_left })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen('renew')}>
              {t('totp.profile.renew')}
            </Button>
            <Button type="button" variant="outline" onClick={() => setOpen('disable')}>
              {t('totp.profile.disable')}
            </Button>
          </div>
        </>
      ) : data.unavailable ? (
        <p className="text-sm text-muted-foreground">
          {data.unavailable === 'no_password'
            ? t('totp.profile.noPassword')
            : t('totp.profile.noSecretKey')}
        </p>
      ) : (
        <>
          <p className="text-sm">{t('totp.profile.off')}</p>
          <div>
            <Button type="button" onClick={() => setOpen('setup')}>
              {t('totp.profile.setUp')}
            </Button>
          </div>
        </>
      )}
      <SetupDialog open={open === 'setup'} onOpenChange={(next) => !next && close()} />
      <CodeDialog
        open={open === 'disable'}
        title={t('totp.disable.title')}
        hint={t('totp.disable.hint')}
        label={t('totp.disable.code')}
        submitLabel={t('totp.disable.submit')}
        destructive
        pending={disable.isPending}
        error={disable.error}
        onSubmit={(typed) => disable.mutate(proofOf(typed), { onSuccess: close })}
        onOpenChange={(next) => !next && close()}
      />
      <CodeDialog
        open={open === 'renew'}
        title={t('totp.renew.title')}
        hint={t('totp.renew.hint')}
        label={t('totp.renew.code')}
        submitLabel={t('totp.renew.submit')}
        pending={renew.isPending}
        error={renew.error}
        done={
          renew.data && (
            <div className="flex flex-col gap-4">
              <RecoveryCodes codes={renew.data} />
              <FormActions>
                <Button type="button" onClick={close}>
                  {t('totp.codes.close')}
                </Button>
              </FormActions>
            </div>
          )
        }
        onSubmit={(typed) => renew.mutate(typed)}
        onOpenChange={(next) => !next && close()}
      />
    </section>
  )
}
