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
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import { useRejectSkillProposal, type SkillProposal } from './queries'

const MAX_REASON = 300

/** Reject a proposal, with an optional reason its author gets to read. */
export function SkillRejectDialog({
  proposal,
  open,
  onOpenChange,
}: {
  proposal: SkillProposal
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const reject = useRejectSkillProposal(proposal.id)
  const [reason, setReason] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const text = reason.trim()
    reject.mutate(
      { version: proposal.version, reason: text === '' ? null : text },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('proposals.reject.title')}</DialogTitle>
          <DialogDescription>{t('skills.proposals.rejectHint')}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field
            label={t('proposals.reject.reason')}
            hint={t('proposals.reject.reasonHint', { count: reason.length, max: MAX_REASON })}
          >
            {(props) => (
              <Textarea
                {...props}
                rows={3}
                maxLength={MAX_REASON}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            )}
          </Field>
          <SaveError error={reject.error} />
          <FormActions>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('actions.cancel')}
            </Button>
            <Button type="submit" variant="destructive" disabled={reject.isPending}>
              {t('proposals.reject.submit')}
            </Button>
          </FormActions>
        </form>
      </DialogContent>
    </Dialog>
  )
}
