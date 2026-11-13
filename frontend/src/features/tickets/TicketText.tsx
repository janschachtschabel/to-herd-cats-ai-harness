import { Pencil } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { MessageMarkdown } from '@/features/messaging/MessageMarkdown'
import { FormActions, SaveError } from '@/features/shared/forms'
import type { Ticket } from '@/lib/api'
import { useTicketSave } from './useTicketSave'

const MAX_TITLE = 200
const MAX_DESCRIPTION = 100_000

/** The title, and with `ticket.edit` a field to change it. */
export function TicketTitle({ ticket, editable }: { ticket: Ticket; editable: boolean }) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<string | null>(null)
  const save = useTicketSave(ticket)
  if (draft === null) {
    return (
      <div className="flex items-start gap-2">
        <h1
          id="ticket-title"
          className="min-w-0 flex-1 text-2xl font-semibold tracking-tight break-words"
        >
          {ticket.title}
        </h1>
        {editable && (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t('tickets.view.editTitle')}
            onClick={() => setDraft(ticket.title)}
          >
            <Pencil aria-hidden />
          </Button>
        )}
      </div>
    )
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const title = draft.trim()
    if (!title || title.length > MAX_TITLE) return
    if (title === ticket.title) return setDraft(null)
    save.mutate({ title }, { onSuccess: () => setDraft(null) })
  }
  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-2"
      aria-label={t('tickets.view.editTitle')}
    >
      <h1 id="ticket-title" className="sr-only">
        {ticket.title}
      </h1>
      <Input
        aria-label={t('tickets.fields.title')}
        value={draft}
        maxLength={MAX_TITLE}
        autoFocus
        onChange={(event) => setDraft(event.target.value)}
      />
      <SaveError error={save.error} onReload={() => void save.reload()} />
      <FormActions>
        <Button type="button" variant="outline" onClick={() => setDraft(null)}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={save.isPending || !draft.trim()}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}

/** The description in Markdown (the messages' safe renderer), and with `ticket.edit`
 *  a field to change it. */
export function TicketDescription({ ticket, editable }: { ticket: Ticket; editable: boolean }) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<string | null>(null)
  const save = useTicketSave(ticket)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (draft === null || draft.length > MAX_DESCRIPTION) return
    if (draft === ticket.description_md) return setDraft(null)
    save.mutate({ description_md: draft }, { onSuccess: () => setDraft(null) })
  }
  return (
    <section aria-labelledby="ticket-description" className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h2 id="ticket-description" className="text-sm font-semibold">
          {t('tickets.fields.description')}
        </h2>
        {editable && draft === null && (
          <Button variant="ghost" size="sm" onClick={() => setDraft(ticket.description_md)}>
            <Pencil aria-hidden />
            {t('tickets.view.editDescription')}
          </Button>
        )}
      </div>
      {draft === null ? (
        ticket.description_md.trim() === '' ? (
          <p className="text-sm text-muted-foreground">{t('tickets.view.noDescription')}</p>
        ) : (
          <MessageMarkdown markdown={ticket.description_md} />
        )
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <Textarea
            aria-label={t('tickets.fields.description')}
            aria-describedby="ticket-description-hint"
            rows={10}
            autoFocus
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <p id="ticket-description-hint" className="text-xs text-muted-foreground">
            {draft.length > MAX_DESCRIPTION
              ? t('validation.tooLong', { count: MAX_DESCRIPTION })
              : t('tickets.fields.markdownHint')}
          </p>
          <SaveError error={save.error} onReload={() => void save.reload()} />
          <FormActions>
            <Button type="button" variant="outline" onClick={() => setDraft(null)}>
              {t('actions.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || draft.length > MAX_DESCRIPTION}>
              {t('actions.save')}
            </Button>
          </FormActions>
        </form>
      )}
    </section>
  )
}
