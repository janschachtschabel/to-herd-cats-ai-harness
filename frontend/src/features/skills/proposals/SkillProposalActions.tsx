import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { movedFrom, movedOf, type Moved } from './moved'
import { useAcceptSkillProposal, type SkillProposalDetail } from './queries'
import { SkillMergeDialog } from './SkillMergeDialog'
import { SkillRejectDialog } from './SkillRejectDialog'

/** Accept and reject for those who decide. Accepting a proposal whose skill moved on
 *  opens the dialog with both texts (from the proposal itself, or from the 409 that
 *  says so); any other refusal is put into words and the proposal reloads. */
export function SkillProposalActions({ proposal }: { proposal: SkillProposalDetail }) {
  const { t } = useTranslation()
  const accept = useAcceptSkillProposal(proposal.id)
  const [moved, setMoved] = useState<Moved | null>(null)
  const [rejecting, setRejecting] = useState(false)

  const onAccept = () => {
    const known = movedOf(proposal)
    if (known) {
      setMoved(known)
      return
    }
    accept.mutate(
      { version: proposal.version },
      {
        onError: (error) => {
          const found = movedFrom(error)
          if (found) {
            accept.reset()
            setMoved(found)
          }
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <Button onClick={onAccept} disabled={accept.isPending}>
          <Check aria-hidden />
          {t('proposals.accept')}
        </Button>
        <Button variant="outline" onClick={() => setRejecting(true)}>
          <X aria-hidden />
          {t('proposals.reject.open')}
        </Button>
      </div>
      <SaveError error={accept.error} />
      <SkillMergeDialog
        proposal={proposal}
        moved={moved}
        onMoved={setMoved}
        onClose={() => setMoved(null)}
      />
      <SkillRejectDialog proposal={proposal} open={rejecting} onOpenChange={setRejecting} />
    </div>
  )
}
