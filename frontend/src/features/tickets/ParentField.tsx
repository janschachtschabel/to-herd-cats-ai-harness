import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import type { Ticket } from '@/lib/api'
import { parentKinds } from './display'
import { FieldRow } from './FieldRow'
import { useParentCandidates } from './queries'
import type { useTicketSave } from './useTicketSave'

/** The epic or story above the ticket; with `ticket.edit` one of the space's epics
 *  (and, for tasks and bugs, stories) can be chosen or the parent removed. An epic has
 *  none (plan M4, decision 5). */
export function ParentField({
  ticket,
  editable,
  save,
}: {
  ticket: Ticket
  editable: boolean
  save: ReturnType<typeof useTicketSave>
}) {
  const { t } = useTranslation()
  const [choosing, setChoosing] = useState(false)
  const kinds = parentKinds(ticket.kind)
  const candidates = useParentCandidates(ticket.space_id, kinds, choosing)
  if (kinds.length === 0) return null
  const options = (candidates.data ?? []).filter((c) => c.id !== ticket.id)
  return (
    <FieldRow label={t('tickets.fields.parent')} editable={choosing}>
      {(id) => (
        <div className="flex flex-col gap-2">
          {choosing ? (
            <NativeSelect
              id={id}
              value={ticket.parent?.id ?? ''}
              disabled={candidates.isPending || save.isPending}
              onChange={(e) => {
                setChoosing(false)
                save.mutate({ parent_id: e.target.value || null })
              }}
            >
              <option value="">{t('tickets.fields.noParent')}</option>
              {ticket.parent && !options.some((o) => o.id === ticket.parent?.id) && (
                <option
                  value={ticket.parent.id}
                >{`${ticket.parent.key} ${ticket.parent.title}`}</option>
              )}
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {`${option.key} ${option.title}`}
                </option>
              ))}
            </NativeSelect>
          ) : ticket.parent ? (
            <Link
              id={id}
              to="/tickets/$number"
              params={{ number: String(ticket.parent.number) }}
              className="truncate text-sm hover:underline"
            >
              <span className="font-mono text-xs text-muted-foreground">{ticket.parent.key}</span>{' '}
              {ticket.parent.title}
            </Link>
          ) : (
            <span id={id} className="text-sm text-muted-foreground">
              {t('tickets.fields.noParent')}
            </span>
          )}
          {editable && (
            <div>
              <Button size="sm" variant="ghost" onClick={() => setChoosing((open) => !open)}>
                {choosing ? t('actions.cancel') : t('tickets.fields.chooseParent')}
              </Button>
            </div>
          )}
        </div>
      )}
    </FieldRow>
  )
}
