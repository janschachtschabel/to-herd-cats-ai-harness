import type { ReactNode } from 'react'
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
import { SaveError } from './forms'

/** Asks before a consequential step; stays open and shows the error if the step fails. */
export function ConfirmDialog({
  open,
  title,
  text,
  confirmLabel,
  destructive = false,
  pending,
  error,
  errorView,
  onConfirm,
  onOpenChange,
}: {
  open: boolean
  title: string
  text: string
  confirmLabel: string
  destructive?: boolean
  pending: boolean
  error: unknown
  /** Shown instead of the standard error box (e.g. a feature's own conflict text). */
  errorView?: ReactNode
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{text}</DialogDescription>
        </DialogHeader>
        {errorView ?? <SaveError error={error} />}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('actions.cancel')}
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            disabled={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
