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

/** Someone saved the page while it was being edited: keep one's own text (on top of
 *  the current version, to save again) or discard it for the current version. */
export function ConflictDialog({
  open,
  busy,
  onKeepMine,
  onDiscardMine,
}: {
  open: boolean
  busy: boolean
  onKeepMine: () => void
  onDiscardMine: () => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open}>
      <DialogContent showCloseButton={false} onEscapeKeyDown={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{t('wiki.editor.conflictTitle')}</DialogTitle>
          <DialogDescription>{t('wiki.editor.conflictText')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onDiscardMine}>
            {t('wiki.editor.discardMine')}
          </Button>
          <Button disabled={busy} onClick={onKeepMine}>
            {t('wiki.editor.keepMine')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
