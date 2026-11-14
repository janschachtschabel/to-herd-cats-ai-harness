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
import { Input } from '@/components/ui/input'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import { MarkdownField } from '../MarkdownField'
import { movedFrom, type Moved } from './moved'
import { useAcceptSkillProposal, type SkillProposalDetail } from './queries'

const MAX_DESCRIPTION = 1024
const MAX_CONTENT = 50_000

/** Accepting a proposal whose skill moved on: the skill as it is now and the proposal
 *  side by side, a final text to edit (it starts as the proposal; either side can be
 *  taken over whole), accepted naming the skill's version. Nothing is taken over
 *  silently: when the skill moves on once more, the dialog starts again. */
export function SkillMergeDialog({
  proposal,
  moved,
  onMoved,
  onClose,
}: {
  proposal: SkillProposalDetail
  moved: Moved | null
  onMoved: (moved: Moved) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [again, setAgain] = useState(false)
  const close = () => {
    setAgain(false)
    onClose()
  }
  return (
    <Dialog open={moved !== null} onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('skills.proposals.merge.title')}</DialogTitle>
          <DialogDescription>{t('skills.proposals.merge.hint')}</DialogDescription>
        </DialogHeader>
        {moved && (
          <MergeForm
            key={moved.skillVersion}
            proposal={proposal}
            moved={moved}
            again={again}
            onMoved={(next) => {
              setAgain(true)
              onMoved(next)
            }}
            onDone={close}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Side({ label, text }: { label: string; text: Moved['current'] }) {
  const { t } = useTranslation()
  return (
    <section aria-label={label} className="flex min-w-0 flex-col gap-1 rounded-lg border p-3">
      <h3 className="text-sm font-medium">{label}</h3>
      <p className="text-xs break-words text-muted-foreground">
        {t('skills.fields.description')}: {text.description}
      </p>
      <pre className="max-h-56 overflow-auto text-xs leading-5 whitespace-pre-wrap">
        {text.content}
      </pre>
    </section>
  )
}

function MergeForm({
  proposal,
  moved,
  again,
  onMoved,
  onDone,
}: {
  proposal: SkillProposalDetail
  moved: Moved
  again: boolean
  onMoved: (moved: Moved) => void
  onDone: () => void
}) {
  const { t } = useTranslation()
  const accept = useAcceptSkillProposal(proposal.id)
  const [description, setDescription] = useState(moved.proposed.description)
  const [content, setContent] = useState(moved.proposed.content)
  const take = (text: Moved['current']) => {
    setDescription(text.description)
    setContent(text.content)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    accept.mutate(
      { version: proposal.version, skill_version: moved.skillVersion, description, content },
      {
        onSuccess: onDone,
        onError: (error) => {
          const next = movedFrom(error)
          if (next) onMoved(next)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      {again && (
        <Alert>
          <AlertDescription>{t('skills.proposals.merge.again')}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <Side label={t('skills.proposals.merge.current')} text={moved.current} />
        <Side label={t('skills.proposals.merge.proposed')} text={moved.proposed} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => take(moved.current)}>
          {t('skills.proposals.merge.takeCurrent')}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => take(moved.proposed)}>
          {t('skills.proposals.merge.takeProposed')}
        </Button>
      </div>
      <Field label={t('skills.fields.description')}>
        {(props) => (
          <Input
            {...props}
            maxLength={MAX_DESCRIPTION}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        )}
      </Field>
      <MarkdownField
        label={t('skills.fields.content')}
        value={content}
        textarea={{
          rows: 10,
          maxLength: MAX_CONTENT,
          value: content,
          onChange: (e) => setContent(e.target.value),
        }}
      />
      <SaveError error={movedFrom(accept.error) ? null : accept.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={accept.isPending}>
          {t('skills.proposals.merge.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
