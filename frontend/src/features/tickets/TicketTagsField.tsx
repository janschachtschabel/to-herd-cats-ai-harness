import { useQuery } from '@tanstack/react-query'
import { Pencil } from 'lucide-react'
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
import { FormActions, SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { spaceTagsQuery } from '@/features/wiki/tags/queries'
import type { Tag, Ticket } from '@/lib/api'
import { useReloadTicket, useSetTicketTags } from './queries'

function TagChip({ tag }: { tag: Tag }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-foreground">
      <span aria-hidden className="size-2 rounded-full" style={{ backgroundColor: tag.color }} />
      {tag.name}
    </span>
  )
}

/** The ticket's tags; with `ticket.edit` they are chosen from the space's tags and the
 *  system-wide ones (at most 20). */
export function TicketTagsField({ ticket, editable }: { ticket: Ticket; editable: boolean }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          {t('tickets.fields.tags')}
        </span>
        {editable && (
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={t('tickets.tags.edit')}
            title={t('tickets.tags.edit')}
            onClick={() => setOpen(true)}
          >
            <Pencil aria-hidden />
          </Button>
        )}
      </div>
      {ticket.tags.length === 0 ? (
        <span className="text-sm text-muted-foreground">{t('tickets.tags.none')}</span>
      ) : (
        <ul className="flex flex-wrap gap-1.5" aria-label={t('tickets.fields.tags')}>
          {ticket.tags.map((tag) => (
            <li key={tag.id}>
              <TagChip tag={tag} />
            </li>
          ))}
        </ul>
      )}
      {editable && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{t('tickets.tags.edit')}</DialogTitle>
              <DialogDescription>{t('tickets.tags.description')}</DialogDescription>
            </DialogHeader>
            {open && <TagsForm ticket={ticket} onDone={() => setOpen(false)} />}
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

function TagsForm({ ticket, onDone }: { ticket: Ticket; onDone: () => void }) {
  const { t } = useTranslation()
  const tags = useQuery(spaceTagsQuery(ticket.space_id))
  const save = useSetTicketTags(ticket)
  const reload = useReloadTicket(ticket.number)
  const [chosen, setChosen] = useState(() => new Set(ticket.tags.map((tag) => tag.id)))
  const toggle = (id: string) =>
    setChosen((before) => {
      const next = new Set(before)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate([...chosen], { onSuccess: onDone })
  }
  if (tags.isPending) return <LoadingState rows={2} />
  if (tags.isError) return <ErrorState error={tags.error} onRetry={() => void tags.refetch()} />
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <fieldset className="flex max-h-72 flex-col gap-1 overflow-y-auto">
        <legend className="sr-only">{t('tickets.fields.tags')}</legend>
        {tags.data.length === 0 && (
          <p className="text-sm text-muted-foreground">{t('tickets.tags.noneAvailable')}</p>
        )}
        {tags.data.map((tag) => (
          <label
            key={tag.id}
            className="flex items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-accent"
          >
            <input
              type="checkbox"
              className="accent-primary"
              checked={chosen.has(tag.id)}
              onChange={() => toggle(tag.id)}
            />
            <span
              aria-hidden
              className="size-2.5 rounded-full"
              style={{ backgroundColor: tag.color }}
            />
            {tag.name}
          </label>
        ))}
      </fieldset>
      <SaveError error={save.error} onReload={() => void reload().then(() => save.reset())} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={save.isPending || chosen.size > 20}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
