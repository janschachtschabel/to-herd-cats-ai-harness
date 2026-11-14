import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import type { Ticket } from '@/lib/api'
import { FieldRow } from '../FieldRow'
import type { useTicketSave } from '../useTicketSave'
import { openSprints, useSprintChoices } from './queries'
import { SprintOption } from './SprintOption'

/** The ticket's sprint: with `ticket.edit` the running or a planned sprint of its
 *  space, or none (the backlog). A closed sprint can be left, not chosen (a ticket
 *  reopened in one goes back to the backlog by itself). */
export function SprintField({
  ticket,
  editable,
  save,
}: {
  ticket: Ticket
  editable: boolean
  save: ReturnType<typeof useTicketSave>
}) {
  const { t } = useTranslation()
  const choices = useSprintChoices(ticket.space_id)
  // The ticket names its own sprint (module review M4b, finding 10), however many
  // sprints its space has; the choices only offer the open ones.
  const current = ticket.sprint
  const name = !current
    ? t('tickets.fields.noSprint')
    : current.state === 'planned'
      ? current.name
      : t(`tickets.sprints.option.${current.state}`, { name: current.name })
  return (
    <FieldRow label={t('tickets.fields.sprint')} editable={editable}>
      {(id) => (
        <>
          {editable ? (
            <NativeSelect
              id={id}
              value={ticket.sprint_id ?? ''}
              disabled={save.isPending || choices.isPending}
              onChange={(e) => save.mutate({ sprint_id: e.target.value || null })}
            >
              <option value="">{t('tickets.fields.noSprint')}</option>
              {openSprints(choices.data).map((sprint) => (
                <SprintOption key={sprint.id} sprint={sprint} />
              ))}
              {current?.state === 'closed' && (
                <option value={current.id} disabled>
                  {name}
                </option>
              )}
            </NativeSelect>
          ) : (
            <span id={id} aria-labelledby={`${id}-label`} className="text-sm">
              {name}
            </span>
          )}
        </>
      )}
    </FieldRow>
  )
}
