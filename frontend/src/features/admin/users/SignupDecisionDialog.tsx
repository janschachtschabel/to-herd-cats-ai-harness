import { useTranslation } from 'react-i18next'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import type { User } from '@/lib/api'
import { useDecideSignup } from './queries'

export interface SignupDecision {
  user: User
  approve: boolean
}

/** Asks before approving (the person may sign in, as a member) or rejecting (the
 *  account stays deactivated) a self-registered account. */
export function SignupDecisionDialog({
  decision,
  onClose,
}: {
  decision: SignupDecision | null
  onClose: () => void
}) {
  const { t } = useTranslation()
  const decide = useDecideSignup()
  const verb = decision?.approve === false ? 'reject' : 'approve'
  return (
    <ConfirmDialog
      open={decision !== null}
      title={t(`users.pending.${verb}.title`)}
      text={t(`users.pending.${verb}.text`, { name: decision?.user.name ?? '' })}
      confirmLabel={t(`users.pending.${verb}.action`)}
      destructive={verb === 'reject'}
      pending={decide.isPending}
      error={decide.error}
      onConfirm={() => decision && decide.mutate(decision, { onSuccess: onClose })}
      onOpenChange={(open) => {
        if (open) return
        decide.reset()
        onClose()
      }}
    />
  )
}
