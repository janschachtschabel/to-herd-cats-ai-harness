import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Field, FormActions } from '@/features/shared/forms'
import type { VersionSummary } from '@/lib/api'
import { WikiError } from '../WikiError'
import { useLabelVersion } from './queries'

export function VersionLabelDialog({
  pageId,
  version,
  onClose,
}: {
  pageId: string
  version: VersionSummary | null
  onClose: () => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={version !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t('wiki.versions.labelTitle', { number: version?.number ?? 0 })}
          </DialogTitle>
        </DialogHeader>
        {version && <LabelForm pageId={pageId} version={version} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  )
}

function LabelForm({
  pageId,
  version,
  onDone,
}: {
  pageId: string
  version: VersionSummary
  onDone: () => void
}) {
  const { t } = useTranslation()
  const label = useLabelVersion(pageId)
  const [value, setValue] = useState(version.label ?? '')

  function submit(event: FormEvent) {
    event.preventDefault()
    label.mutate({ number: version.number, label: value.trim() || null }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label={t('wiki.versions.label')} hint={t('wiki.versions.labelHint')}>
        {(props) => (
          <Input
            {...props}
            autoFocus
            maxLength={100}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        )}
      </Field>
      <WikiError error={label.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={label.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
