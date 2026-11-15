import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
import { ConflictRegion } from './ConflictRegion'
import {
  conflictCount,
  conflictsOf,
  mergedText,
  outdatedFrom,
  startText,
  type Choice,
  type Outdated,
} from './merge'
import { PageChanges } from './PageChanges'
import { useAcceptProposal, type ProposalDetail } from './queries'

/** Accepting a proposal whose page moved on: what changed on the page meanwhile, the
 *  clean merge or the conflict regions (each resolved by an explicit choice), and the
 *  merged text to edit and accept, naming the page's version. Nothing is ever taken
 *  over silently: when the page moves on once more, the dialog starts again. */
export function MergeDialog({
  proposal,
  outdated,
  onOutdated,
  onClose,
}: {
  proposal: ProposalDetail
  outdated: Outdated | null
  onOutdated: (outdated: Outdated) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [again, setAgain] = useState(false)
  const close = () => {
    setAgain(false)
    onClose()
  }
  return (
    <Dialog open={outdated !== null} onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('proposals.merge.title')}</DialogTitle>
          <DialogDescription>{t('proposals.merge.hint')}</DialogDescription>
        </DialogHeader>
        {outdated && (
          <MergeForm
            key={outdated.pageVersion}
            proposal={proposal}
            outdated={outdated}
            again={again}
            onOutdated={(moved) => {
              setAgain(true)
              onOutdated(moved)
            }}
            onDone={close}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function MergeForm({
  proposal,
  outdated,
  again,
  onOutdated,
  onDone,
}: {
  proposal: ProposalDetail
  outdated: Outdated
  again: boolean
  onOutdated: (outdated: Outdated) => void
  onDone: () => void
}) {
  const { t } = useTranslation()
  const accept = useAcceptProposal(proposal)
  const conflicts = conflictCount(outdated.segments)
  const [choices, setChoices] = useState<Choice[]>(() => Array<Choice>(conflicts).fill('current'))
  const [text, setText] = useState(() => startText(outdated, choices))

  const choose = (index: number, choice: Choice) => {
    const next = choices.map((c, i) => (i === index ? choice : c))
    setChoices(next)
    setText(mergedText(outdated.segments, next))
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    accept.mutate(
      { version: proposal.version, merged_content: text, page_version: outdated.pageVersion },
      {
        onSuccess: onDone,
        onError: (error) => {
          const moved = outdatedFrom(error)
          if (moved) onOutdated(moved)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      {again && (
        <Alert>
          <AlertDescription>{t('proposals.merge.again')}</AlertDescription>
        </Alert>
      )}
      {proposal.page_id && (
        <PageChanges pageId={proposal.page_id} baseVersion={proposal.base_version} />
      )}
      {outdated.tooLarge ? (
        <p className="text-sm">{t('proposals.merge.tooLarge')}</p>
      ) : (
        <>
          <p className="text-sm">
            {conflicts === 0
              ? t('proposals.merge.clean')
              : t('proposals.merge.conflicts', { count: conflicts })}
          </p>
          {conflictsOf(outdated.segments).map((segment, at) => (
            <ConflictRegion
              key={at}
              number={at + 1}
              segment={segment}
              choice={choices[at] ?? 'current'}
              onChoose={(choice) => choose(at, choice)}
            />
          ))}
          <Field label={t('proposals.merge.text')} hint={t('proposals.merge.textHint')}>
            {(props) => (
              <Textarea
                {...props}
                rows={10}
                className="font-mono text-xs"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            )}
          </Field>
        </>
      )}
      <SaveError error={outdatedFrom(accept.error) ? null : accept.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        {!outdated.tooLarge && (
          <Button type="submit" disabled={accept.isPending}>
            {t('proposals.merge.submit')}
          </Button>
        )}
      </FormActions>
    </form>
  )
}
