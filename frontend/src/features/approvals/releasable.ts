import { useApprovalDiff, type Approval } from './queries'

/** Whether the person asked may release the call from this card: not a personal one
 *  whose content cannot be shown in full (its diff beyond the limit; the server
 *  refuses it too, `approval.not_shown_in_full`). */
export function useReleasable(approval: Approval): boolean {
  const personal = approval.personal === true && approval.args !== null
  const diff = useApprovalDiff(approval.id, personal && approval.diff_url !== null)
  return !(personal && approval.diff_url !== null && diff.data === null)
}
