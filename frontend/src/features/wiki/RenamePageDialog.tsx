import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Field, FormActions } from '@/features/shared/forms'
import type { WikiPage } from '@/lib/api'
import { useUpdatePage } from './queries'
import { WikiError } from './WikiError'

/** A new title; slug and path stay, so links to the page keep working. */
export function RenamePageDialog({
  page,
  open,
  onOpenChange,
}: {
  page: WikiPage
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('wiki.rename.title')}</DialogTitle>
        </DialogHeader>
        {open && <RenameForm page={page} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function RenameForm({ page, onDone }: { page: WikiPage; onDone: () => void }) {
  const { t } = useTranslation()
  const update = useUpdatePage(page)
  const [title, setTitle] = useState(page.title)
  const blank = title.trim() === ''

  function submit(event: FormEvent) {
    event.preventDefault()
    if (blank) return
    update.mutate({ title: title.trim(), version: page.version }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <Field label={t('wiki.fields.title')} error={blank ? t('validation.required') : undefined}>
        {(props) => (
          <Input
            {...props}
            autoFocus
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        )}
      </Field>
      <WikiError error={update.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={update.isPending || blank}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
