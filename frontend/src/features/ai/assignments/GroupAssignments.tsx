import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { chatConnections, type Connection } from '../display'
import { useSetGroups } from '../assignmentQueries'
import { groupsBody, moved, type GroupRow } from './order'
import { TargetPicker } from './TargetPicker'

/** The ordered group list: for a person in several groups the first one wins. Edited
 *  here and saved as a whole (one version with the standard). */
export function GroupAssignments({
  initial,
  version,
  connections,
  onReload,
}: {
  initial: readonly Schemas['GroupAssignmentOut'][]
  version: number
  connections: readonly Connection[]
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetGroups()
  const [rows, setRows] = useState<GroupRow[]>(() =>
    initial.map((g) => ({
      group_id: g.group_id,
      group_name: g.group_name,
      connection_id: g.target.connection_id,
      model: g.target.model,
    })),
  )
  const [saved, setSaved] = useState(false)
  const present = useMemo(() => new Set(rows.map((r) => `group:${r.group_id}`)), [rows])
  const first = chatConnections(connections)[0]
  const change = (next: GroupRow[]) => {
    setRows(next)
    setSaved(false)
  }

  return (
    <section aria-labelledby="ai-groups-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="ai-groups-heading" className="font-semibold">
          {t('ai.assignments.groupsTitle')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('ai.assignments.groupsHint')}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('ai.assignments.groupsEmpty')}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((row, index) => (
            <li key={row.group_id} className="flex flex-col gap-2 rounded-lg border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">
                  {index + 1}. {row.group_name}
                </span>
                <div className="flex gap-1">
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    disabled={index === 0}
                    aria-label={t('ai.assignments.moveUp', { name: row.group_name })}
                    onClick={() => change(moved(rows, index, -1))}
                  >
                    <ArrowUp aria-hidden />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    disabled={index === rows.length - 1}
                    aria-label={t('ai.assignments.moveDown', { name: row.group_name })}
                    onClick={() => change(moved(rows, index, 1))}
                  >
                    <ArrowDown aria-hidden />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={t('ai.assignments.removeGroup', { name: row.group_name })}
                    onClick={() => change(rows.filter((r) => r.group_id !== row.group_id))}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </div>
              </div>
              <TargetPicker
                connections={connections}
                value={row}
                label={row.group_name}
                onChange={(target) =>
                  target &&
                  change(rows.map((r) => (r.group_id === row.group_id ? { ...r, ...target } : r)))
                }
              />
            </li>
          ))}
        </ol>
      )}
      {first && (
        <Field label={t('ai.assignments.addGroup')}>
          {(props) => (
            <DirectoryCombobox
              control={props}
              type="group"
              selected={null}
              exclude={present}
              onSelect={(entry) =>
                entry &&
                change([
                  ...rows,
                  {
                    group_id: entry.id,
                    group_name: entry.name,
                    connection_id: first.id,
                    model: first.models[0] ?? '',
                  },
                ])
              }
            />
          )}
        </Field>
      )}
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          disabled={save.isPending}
          onClick={() =>
            save.mutate(groupsBody(rows, version), { onSuccess: () => setSaved(true) })
          }
        >
          {t('ai.assignments.saveGroups')}
        </Button>
        {saved && (
          <span role="status" className="text-sm text-muted-foreground">
            {t('ai.assignments.saved')}
          </span>
        )}
      </div>
      <SaveError
        error={save.error}
        onReload={() => {
          save.reset()
          onReload()
        }}
      />
    </section>
  )
}
