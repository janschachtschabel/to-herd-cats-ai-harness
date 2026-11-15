import { useState, type FormEvent, type ReactNode } from 'react'
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
import { reasonKey, useImportSkills, type SkillImport } from './queries'

/** Import a SKILL.md or a ZIP of skill folders into a space (or the organisation:
 *  `spaceId` null). Each skill is reported: created (with the front matter fields
 *  that were not kept) or skipped with its reason. Nothing in a skill is run. */
export function ImportSkillsDialog({
  open,
  spaceId,
  where,
  onOpenChange,
}: {
  open: boolean
  spaceId: string | null
  where?: ReactNode
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('skills.import.title')}</DialogTitle>
          <DialogDescription>{t('skills.import.description')}</DialogDescription>
        </DialogHeader>
        {open && <ImportForm spaceId={spaceId} where={where} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function ImportForm({
  spaceId,
  where,
  onDone,
}: {
  spaceId: string | null
  where?: ReactNode
  onDone: () => void
}) {
  const { t } = useTranslation()
  const run = useImportSkills(spaceId)
  const [file, setFile] = useState<File | null>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (file) run.mutate(file)
  }

  if (run.data) return <ImportResult result={run.data} onDone={onDone} />
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Alert>
        <AlertDescription>{t('skills.import.safe')}</AlertDescription>
      </Alert>
      {where}
      <Field label={t('skills.import.file')} hint={t('skills.import.fileHint')}>
        {(props) => (
          <Input
            {...props}
            type="file"
            accept=".md,.zip,text/markdown,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </Field>
      <SaveError error={run.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={!file || run.isPending}>
          {t('skills.import.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function ImportResult({ result, onDone }: { result: SkillImport; onDone: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-4 text-sm">
      {/* The result stands beside the reminder that nothing of a skill runs. */}
      <Alert>
        <AlertDescription>{t('skills.import.safe')}</AlertDescription>
      </Alert>
      <section aria-labelledby="import-created">
        <h3 id="import-created" className="mb-1 font-medium">
          {t('skills.import.created', { count: result.created.length })}
        </h3>
        <ul className="flex flex-col gap-1">
          {result.created.map((c) => (
            <li key={c.skill_id}>
              <span className="font-medium">{c.name}</span>{' '}
              <span className="text-muted-foreground">({c.path})</span>
              {c.ignored_fields.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t('skills.import.ignored', { fields: c.ignored_fields.join(', ') })}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>
      {result.skipped.length > 0 && (
        <section aria-labelledby="import-skipped">
          <h3 id="import-skipped" className="mb-1 font-medium">
            {t('skills.import.skipped', { count: result.skipped.length })}
          </h3>
          <ul className="flex flex-col gap-1">
            {result.skipped.map((s) => (
              <li key={`${s.path}-${s.reason}`}>
                <span className="font-mono text-xs break-all">{s.path}</span>
                <p className="text-xs text-muted-foreground">
                  {t(`skills.import.reasons.${reasonKey(s.reason)}`, {
                    defaultValue: t('skills.import.reasons.unknown'),
                  })}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
      <FormActions>
        <Button onClick={onDone}>{t('actions.close')}</Button>
      </FormActions>
    </div>
  )
}
