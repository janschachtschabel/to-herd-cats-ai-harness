import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useMe } from '@/features/auth/queries'
import { Field, SaveError } from '@/features/shared/forms'
import { useReplaceInstallation } from './queries'

/** Replacing the whole installation, confirmed by typing the organisation's name (the
 *  name is shown: it is what the command line's `--confirm` takes too). */
export function ReplaceDialog({
  archive,
  onOpenChange,
  onStarted,
}: {
  archive: string | null
  onOpenChange: (open: boolean) => void
  onStarted: () => void
}) {
  const { t } = useTranslation()
  const org = useMe()?.org.name ?? ''
  const [typed, setTyped] = useState('')
  const replace = useReplaceInstallation()
  const close = (open: boolean) => {
    if (!open) {
      setTyped('')
      replace.reset()
    }
    onOpenChange(open)
  }
  return (
    <Dialog open={archive !== null} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('backup.replace.title')}</DialogTitle>
          <DialogDescription>{t('backup.replace.text', { name: archive ?? '' })}</DialogDescription>
        </DialogHeader>
        <Field label={t('backup.replace.confirm', { org })}>
          {(props) => (
            <Input
              {...props}
              autoComplete="off"
              spellCheck={false}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
          )}
        </Field>
        <SaveError error={replace.error} />
        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {t('actions.cancel')}
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== org || org === '' || replace.isPending || archive === null}
            onClick={() => {
              if (archive === null) return
              replace.mutate(
                { name: archive, confirm: typed },
                {
                  onSuccess: () => {
                    close(false)
                    onStarted()
                  },
                },
              )
            }}
          >
            {t('backup.replace.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
