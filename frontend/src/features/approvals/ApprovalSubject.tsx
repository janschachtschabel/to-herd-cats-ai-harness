import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ticketKey } from '@/features/tickets/refs'
import { DiffLines } from '@/features/wiki/versions/DiffLines'
import { errorMessage } from '@/lib/errors'
import { shownArgs, subjectsOf } from './display'
import { useApprovalDiff, type Approval } from './queries'

/** An external call's arguments: exactly what goes to the server, open, for the person
 *  asked (the API sends them to no one else). */
function ExternalArgs({ approval }: { approval: Approval }) {
  const { t } = useTranslation()
  if (!approval.args) {
    return <p className="text-xs text-muted-foreground">{t('approvals.card.externalArgsHidden')}</p>
  }
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs">{t('approvals.card.externalArgs')}</p>
      <pre
        aria-label={t('approvals.card.externalArgsLabel')}
        className="max-h-60 overflow-auto rounded-md border bg-muted/30 p-2 font-mono text-xs break-words whitespace-pre-wrap"
      >
        {JSON.stringify(approval.args, null, 2)}
      </pre>
    </div>
  )
}

/** What a call would change: links to the page and the ticket it names, the page's
 *  diff (the page as it is now against the call's content; for the person asked,
 *  loaded when opened) and the call's other arguments, folded. An external call names
 *  nothing of ours: its arguments are shown as they go to the server. */
export function ApprovalSubject({ approval }: { approval: Approval }) {
  if (approval.external) return <ExternalArgs approval={approval} />
  return <InternalSubject approval={approval} />
}

function InternalSubject({ approval }: { approval: Approval }) {
  const { t } = useTranslation()
  const [diffOpen, setDiffOpen] = useState(false)
  const diff = useApprovalDiff(approval.id, diffOpen && approval.diff_url !== null)
  const { pageId, ticketNumber } = subjectsOf(approval)
  const args = shownArgs(approval)
  const link = 'text-xs font-medium underline underline-offset-2'
  return (
    <div className="flex flex-col gap-2">
      {(pageId || ticketNumber) && (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          {pageId && (
            <Link to="/go/page/$pageId" params={{ pageId }} className={link}>
              {t('approvals.card.openPage')}
            </Link>
          )}
          {ticketNumber && (
            <Link to="/tickets/$number" params={{ number: String(ticketNumber) }} className={link}>
              {t('approvals.card.openTicket', { key: ticketKey(ticketNumber) })}
            </Link>
          )}
        </p>
      )}
      {approval.diff_url && (
        <div>
          <Button
            variant="outline"
            size="xs"
            aria-expanded={diffOpen}
            onClick={() => setDiffOpen((open) => !open)}
          >
            {diffOpen ? t('approvals.card.hideDiff') : t('approvals.card.showDiff')}
          </Button>
          {diffOpen &&
            (diff.isPending ? (
              <p className="mt-1 text-xs text-muted-foreground">{t('states.loading')}</p>
            ) : diff.isError ? (
              <p role="alert" className="mt-1 text-xs text-destructive">
                {errorMessage(t, diff.error)}
              </p>
            ) : diff.data === null ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {t('approvals.card.diffTooLarge')}
              </p>
            ) : (
              <div className="mt-1 max-h-80 overflow-auto">
                <DiffLines hunks={diff.data} />
              </div>
            ))}
        </div>
      )}
      {args && Object.keys(args).length > 0 && (
        <details className="rounded-md border bg-muted/30 text-xs">
          <summary className="cursor-pointer px-2 py-1 font-medium select-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none">
            {t('approvals.card.args')}
          </summary>
          <pre className="max-h-60 overflow-auto px-2 pb-2 font-mono break-words whitespace-pre-wrap">
            {JSON.stringify(args, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
