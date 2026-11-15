import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { MergeDialog } from './MergeDialog'
import { outdatedFrom, type Outdated } from './merge'
import { RejectDialog } from './RejectDialog'
import { useAcceptProposal, type ProposalDetail } from './queries'

/** Accept and reject for moderators. Accepting a proposal whose page moved on opens
 *  the merge dialog (from the proposal's own merge, or from the 409 that says so);
 *  any other refusal is put into words, and the proposal is reloaded. */
export function ProposalActions({
  proposal,
  outdated,
}: {
  proposal: ProposalDetail
  outdated: Outdated | null
}) {
  const { t } = useTranslation()
  const accept = useAcceptProposal(proposal)
  const [merging, setMerging] = useState<Outdated | null>(null)
  const [rejecting, setRejecting] = useState(false)

  const onAccept = () => {
    if (outdated) {
      setMerging(outdated)
      return
    }
    accept.mutate(
      { version: proposal.version },
      {
        onError: (error) => {
          const moved = outdatedFrom(error)
          if (moved) {
            accept.reset()
            setMerging(moved)
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
      <MergeDialog
        proposal={proposal}
        outdated={merging}
        onOutdated={setMerging}
        onClose={() => setMerging(null)}
      />
      <RejectDialog proposal={proposal} open={rejecting} onOpenChange={setRejecting} />
    </div>
  )
}
