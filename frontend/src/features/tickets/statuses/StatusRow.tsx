import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { SaveError } from '@/features/shared/forms'
import type { TicketStatus } from '@/lib/api'
import { CATEGORIES, type StatusCategory } from '../display'
import { DeleteStatusDialog } from './DeleteStatusDialog'
import { useUpdateStatus } from './queries'

/** One status: its name (saved with Enter or "save"), its category, moving it up or
 *  down, deleting it. A stale version says so; reloading keeps the typed name. */
export function StatusRow({
  status,
  others,
  first,
  last,
}: {
  status: TicketStatus
  others: TicketStatus[]
  first: boolean
  last: boolean
}) {
  const { t } = useTranslation()
  const update = useUpdateStatus(status)
  const [name, setName] = useState(status.name)
  const [deleting, setDeleting] = useState(false)
  const dirty = name.trim() !== status.name && name.trim() !== ''
  const rename = (event: FormEvent) => {
    event.preventDefault()
    if (dirty) update.mutate({ name: name.trim() })
  }
  return (
    <li className="flex flex-col gap-2 p-2">
      <form onSubmit={rename} className="flex flex-wrap items-center gap-2">
        <Input
          aria-label={t('tickets.statuses.nameOf', { name: status.name })}
          maxLength={40}
          className="min-w-32 flex-1"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {dirty && (
          <Button type="submit" size="sm" disabled={update.isPending}>
            {t('actions.save')}
          </Button>
        )}
        <div className="w-36">
          <NativeSelect
            aria-label={t('tickets.statuses.categoryOf', { name: status.name })}
            value={status.category}
            disabled={update.isPending}
            onChange={(e) => update.mutate({ category: e.target.value as StatusCategory })}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`tickets.categories.${c}`)}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t('tickets.statuses.up', { name: status.name })}
            disabled={first || update.isPending}
            onClick={() => update.mutate({ position: status.position - 1 })}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t('tickets.statuses.down', { name: status.name })}
            disabled={last || update.isPending}
            onClick={() => update.mutate({ position: status.position + 1 })}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t('tickets.statuses.delete', { name: status.name })}
            onClick={() => setDeleting(true)}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </form>
      <SaveError error={update.error} onReload={() => update.reset()} />
      <DeleteStatusDialog
        status={status}
        others={others}
        open={deleting}
        onOpenChange={setDeleting}
      />
    </li>
  )
}
