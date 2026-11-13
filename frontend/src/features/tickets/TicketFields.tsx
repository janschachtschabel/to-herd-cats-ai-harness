import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { SaveError } from '@/features/shared/forms'
import type { Ticket } from '@/lib/api'
import type { TicketAbilities } from './abilities'
import { AssigneeField } from './AssigneeField'
import { FieldRow } from './FieldRow'
import { KINDS, PRIORITIES, type Priority, type TicketKind } from './display'
import { LinkedPages } from './links/LinkedPages'
import { ParentField } from './ParentField'
import { DueLabel, KindLabel, PriorityLabel, StatusBadge } from './parts'
import { useStatuses } from './queries'
import { TicketTagsField } from './TicketTagsField'
import { useTicketSave } from './useTicketSave'

/** The ticket's fields beside it: status, assignee, priority, kind, due day, parent,
 *  tags and linked pages. Each change is saved at once against the version read; when
 *  someone changed the ticket in the meantime, the view says so and offers to reload. */
export function TicketFields({
  ticket,
  abilities,
  meId,
}: {
  ticket: Ticket
  abilities: TicketAbilities
  meId: string | undefined
}) {
  const { t } = useTranslation()
  const save = useTicketSave(ticket)
  const statuses = useStatuses(ticket.space_id)
  const edit = abilities.edit
  return (
    <aside
      aria-label={t('tickets.view.fields')}
      className="flex flex-col gap-4 rounded-lg border p-3 lg:self-start"
    >
      <SaveError error={save.error} onReload={() => void save.reload()} />
      <FieldRow label={t('tickets.fields.status')} editable={edit}>
        {(id) =>
          edit ? (
            <NativeSelect
              id={id}
              value={ticket.status.id}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ status_id: e.target.value })}
            >
              {(statuses.data ?? [ticket.status]).map((status) => (
                <option key={status.id} value={status.id}>
                  {status.name}
                </option>
              ))}
            </NativeSelect>
          ) : (
            <span id={id} aria-labelledby={`${id}-label`}>
              <StatusBadge status={ticket.status} />
            </span>
          )
        }
      </FieldRow>
      <AssigneeField ticket={ticket} abilities={abilities} meId={meId} save={save} />
      <FieldRow label={t('tickets.fields.priority')} editable={edit}>
        {(id) =>
          edit ? (
            <NativeSelect
              id={id}
              value={ticket.priority}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ priority: e.target.value as Priority })}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {t(`tickets.priorities.${p}`)}
                </option>
              ))}
            </NativeSelect>
          ) : (
            <span id={id} aria-labelledby={`${id}-label`}>
              <PriorityLabel priority={ticket.priority} />
            </span>
          )
        }
      </FieldRow>
      <FieldRow label={t('tickets.fields.kind')} editable={edit}>
        {(id) =>
          edit ? (
            <NativeSelect
              id={id}
              value={ticket.kind}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ kind: e.target.value as TicketKind })}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`tickets.kinds.${k}`)}
                </option>
              ))}
            </NativeSelect>
          ) : (
            <span id={id} aria-labelledby={`${id}-label`}>
              <KindLabel kind={ticket.kind} />
            </span>
          )
        }
      </FieldRow>
      <FieldRow label={t('tickets.fields.due')} editable={edit}>
        {(id) =>
          edit ? (
            <Input
              id={id}
              type="date"
              // Re-mounted when the server's day changes, so the field shows it again.
              key={ticket.due_on ?? 'none'}
              defaultValue={ticket.due_on ?? ''}
              disabled={save.isPending}
              onBlur={(e) => {
                const due = e.target.value || null
                if (due !== ticket.due_on) save.mutate({ due_on: due })
              }}
            />
          ) : (
            <span id={id} aria-labelledby={`${id}-label`}>
              {ticket.due_on ? <DueLabel due={ticket.due_on} /> : t('tickets.fields.noDue')}
            </span>
          )
        }
      </FieldRow>
      <ParentField ticket={ticket} editable={edit} save={save} />
      <TicketTagsField ticket={ticket} editable={edit} />
      <LinkedPages ticket={ticket} editable={edit} />
    </aside>
  )
}
