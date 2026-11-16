import { useTranslation } from 'react-i18next'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import type { User } from '@/lib/api'
import { useResetTotp } from './queries'

/** Asks before turning a person's two-factor sign-in off (a lost device): the admin
 *  is to make sure who asks. */
export function TotpResetDialog({ person, onClose }: { person: User | null; onClose: () => void }) {
  const { t } = useTranslation()
  const reset = useResetTotp()
  const name = person?.name ?? ''
  return (
    <ConfirmDialog
      open={person !== null}
      title={t('totp.admin.resetTitle', { name })}
      text={t('totp.admin.resetText', { name })}
      confirmLabel={t('totp.admin.resetConfirm')}
      destructive
      pending={reset.isPending}
      error={reset.error}
      onConfirm={() => person && reset.mutate(person.id, { onSuccess: onClose })}
      onOpenChange={(open) => {
        if (!open) {
          reset.reset()
          onClose()
        }
      }}
    />
  )
}
