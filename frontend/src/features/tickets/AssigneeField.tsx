import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import type { Ticket } from '@/lib/api'
import { canRelease, canTake, type TicketAbilities } from './abilities'
import { AssigneeLabel } from './parts'
import { FieldRow } from './FieldRow'
import { PickupBadge } from './PickupBadge'
import type { useTicketSave } from './useTicketSave'

const NONE = new Set<string>()

/** Who works on it. "Take" for an unassigned ticket (`ticket.edit`), "Let go" for
 *  one's own (or anyone's with `ticket.assign`), and with `ticket.assign` a picker of
 *  the people who may read the space's tickets and, for people with AI, the space's
 *  member agents (the directory offers them; the API refuses the rest). */
export function AssigneeField({
  ticket,
  abilities,
  meId,
  save,
}: {
  ticket: Ticket
  abilities: TicketAbilities
  meId: string | undefined
  save: ReturnType<typeof useTicketSave>
}) {
  const { t } = useTranslation()
  const [picking, setPicking] = useState(false)
  const take = canTake(ticket, abilities) && meId !== undefined
  const release = canRelease(ticket, abilities, meId)
  return (
    <FieldRow label={t('tickets.fields.assignee')} editable={picking}>
      {(id) => (
        <div className="flex flex-col gap-2">
          {picking ? (
            <DirectoryCombobox
              control={{ id }}
              selected={null}
              exclude={NONE}
              spaceId={ticket.space_id}
              onSelect={(entry) => {
                if (!entry || entry.type === 'group') return
                setPicking(false)
                save.mutate({ assignee: { type: entry.type, id: entry.id } })
              }}
            />
          ) : (
            <span id={id} aria-labelledby={`${id}-label`} className="flex flex-col gap-1">
              <AssigneeLabel assignee={ticket.assignee} />
              {ticket.awaiting_pickup && (
                <span>
                  <PickupBadge />
                </span>
              )}
            </span>
          )}
          <div className="flex flex-wrap gap-1.5">
            {take && (
              <Button
                size="sm"
                variant="outline"
                disabled={save.isPending}
                onClick={() => save.mutate({ assignee: { type: 'user', id: meId } })}
              >
                {t('tickets.assign.take')}
              </Button>
            )}
            {release && (
              <Button
                size="sm"
                variant="ghost"
                disabled={save.isPending}
                onClick={() => save.mutate({ assignee: null })}
              >
                {ticket.assignee?.id === meId
                  ? t('tickets.assign.release')
                  : t('tickets.assign.clear')}
              </Button>
            )}
            {abilities.assign && (
              <Button size="sm" variant="ghost" onClick={() => setPicking((open) => !open)}>
                {picking ? t('actions.cancel') : t('tickets.assign.choose')}
              </Button>
            )}
          </div>
        </div>
      )}
    </FieldRow>
  )
}
