import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { TicketStatus } from '@/lib/api'
import { useDeleteStatus } from './queries'

/** Deleting a status names where its tickets go (another status of the space); the
 *  server refuses to leave the space without an open or a done status. */
export function DeleteStatusDialog({
  status,
  others,
  open,
  onOpenChange,
}: {
  status: TicketStatus
  others: TicketStatus[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const remove = useDeleteStatus(status)
  const [target, setTarget] = useState(others[0]?.id ?? '')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('tickets.statuses.deleteTitle', { name: status.name })}</DialogTitle>
          <DialogDescription>{t('tickets.statuses.deleteText')}</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (target) remove.mutate(target, { onSuccess: () => onOpenChange(false) })
          }}
        >
          <Field label={t('tickets.statuses.replaceWith')}>
            {(props) => (
              <NativeSelect {...props} value={target} onChange={(e) => setTarget(e.target.value)}>
                {others.map((other) => (
                  <option key={other.id} value={other.id}>
                    {other.name}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
          <SaveError error={remove.error} onReload={() => remove.reset()} />
          <FormActions>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('actions.cancel')}
            </Button>
            <Button type="submit" variant="destructive" disabled={!target || remove.isPending}>
              {t('actions.delete')}
            </Button>
          </FormActions>
        </form>
      </DialogContent>
    </Dialog>
  )
}
