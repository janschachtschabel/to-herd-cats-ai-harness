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
import { Input } from '@/components/ui/input'
import { Field, FormActions } from '@/features/shared/forms'
import type { ImportResult } from '@/lib/api'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { useImportSpace } from './queries'

export function ImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('wiki.transfer.importTitle')}</DialogTitle>
          <DialogDescription>{t('wiki.transfer.importDescription')}</DialogDescription>
        </DialogHeader>
        {open && <ImportForm onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function ImportForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const { space } = useWiki()
  const run = useImportSpace(space.id)
  const [file, setFile] = useState<File | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (file) run.mutate(file)
  }

  if (run.data) return <ImportSummary result={run.data} onDone={onDone} />
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label={t('wiki.transfer.file')}>
        {(props) => (
          <Input
            {...props}
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </Field>
      <WikiError error={run.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={!file || run.isPending}>
          {run.isPending ? t('wiki.transfer.importing') : t('wiki.transfer.importSubmit')}
        </Button>
      </FormActions>
    </form>
  )
}

function ImportSummary({ result, onDone }: { result: ImportResult; onDone: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-3 text-sm" role="status">
      <p>{t('wiki.transfer.created', { count: result.created })}</p>
      <p>{t('wiki.transfer.attachments', { count: result.attachments })}</p>
      {result.skipped.length > 0 && (
        <div>
          <p className="font-medium">
            {t('wiki.transfer.skipped', { count: result.skipped.length })}
          </p>
          <ul className="mt-1 max-h-48 list-disc overflow-y-auto pl-5">
            {result.skipped.map((entry) => (
              <li key={`${entry.path}-${entry.reason}`}>
                <span className="font-mono text-xs">{entry.path}</span> –{' '}
                {t(`wiki.transfer.reasons.${entry.reason}`, { defaultValue: entry.reason })}
              </li>
            ))}
          </ul>
        </div>
      )}
      <FormActions>
        <Button onClick={onDone}>{t('actions.close')}</Button>
      </FormActions>
    </div>
  )
}
