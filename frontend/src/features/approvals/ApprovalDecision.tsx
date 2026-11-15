import { Check, X } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { useDecideApproval, Approval } from './queries'

const MAX_REASON = 500

/** Approve, or reject with an optional reason, at the version the card shows. The
 *  card holds the decision, so a refusal stays in words after the card reloads. */
export function ApprovalDecision({
  approval,
  decide,
}: {
  approval: Approval
  decide: ReturnType<typeof useDecideApproval>
}) {
  const { t } = useTranslation()
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const reasonId = useId()
  const tooLong = reason.length > MAX_REASON

  return (
    <div className="flex flex-col gap-2">
      {rejecting ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (tooLong) return
            decide.mutate({
              decision: 'reject',
              reason: reason.trim() || null,
              version: approval.version,
            })
          }}
        >
          <Label htmlFor={reasonId}>{t('approvals.decide.reason')}</Label>
          <Textarea
            id={reasonId}
            value={reason}
            rows={2}
            aria-invalid={tooLong || undefined}
            onChange={(event) => setReason(event.target.value)}
          />
          {tooLong && (
            <p className="text-xs text-destructive">
              {t('approvals.decide.reasonTooLong', { count: MAX_REASON })}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" variant="destructive" disabled={decide.isPending}>
              {t('approvals.decide.rejectConfirm')}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRejecting(false)}>
              {t('actions.cancel')}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ decision: 'approve', version: approval.version })}
          >
            <Check aria-hidden />
            {t('approvals.decide.approve')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={decide.isPending}
            onClick={() => setRejecting(true)}
          >
            <X aria-hidden />
            {t('approvals.decide.reject')}
          </Button>
        </div>
      )}
    </div>
  )
}
