import { Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, SaveError } from '@/features/shared/forms'
import { ErrorState, LoadMore } from '@/features/shared/states'
import type { DirectoryEntry } from '@/lib/api'
import type { Connection } from '../display'
import {
  useRemoveUserAssignment,
  useSetUserAssignment,
  useUserAssignments,
} from '../assignmentQueries'
import { TargetPicker, type Target } from './TargetPicker'

/** Assignments of single people: a model of their own, or explicitly no AI. They win
 *  over groups and the standard. */
export function UserAssignments({ connections }: { connections: readonly Connection[] }) {
  const { t } = useTranslation()
  const list = useUserAssignments()
  const set = useSetUserAssignment()
  const remove = useRemoveUserAssignment()
  const [person, setPerson] = useState<DirectoryEntry | null>(null)
  const [target, setTarget] = useState<Target | null>(null)
  const present = useMemo(() => new Set(list.items.map((u) => `user:${u.user_id}`)), [list.items])

  const add = () => {
    if (!person) return
    set.mutate(
      {
        userId: person.id,
        body: target ? { target, version: null } : { no_ai: true, version: null },
      },
      {
        onSuccess: () => {
          setPerson(null)
          setTarget(null)
        },
      },
    )
  }

  return (
    <section aria-labelledby="ai-users-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="ai-users-heading" className="font-semibold">
          {t('ai.assignments.usersTitle')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('ai.assignments.usersHint')}</p>
      </div>
      {list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : list.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('ai.assignments.usersEmpty')}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {list.items.map((row) => (
            <li key={row.user_id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 font-medium">{row.user_name}</span>
              <span className="text-muted-foreground">
                {row.no_ai || !row.target
                  ? t('ai.assignments.noAi')
                  : t('ai.assignments.targetText', {
                      connection: row.target.connection_name,
                      model: row.target.model,
                    })}
              </span>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={t('ai.assignments.removePerson', { name: row.user_name })}
                disabled={remove.isPending}
                onClick={() => remove.mutate({ userId: row.user_id, version: row.version })}
              >
                <Trash2 aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
      <SaveError error={remove.error} />
      <div className="flex flex-col gap-3 rounded-lg border p-3">
        <Field label={t('ai.assignments.person')}>
          {(props) => (
            <DirectoryCombobox
              control={props}
              type="user"
              selected={person}
              exclude={present}
              onSelect={setPerson}
            />
          )}
        </Field>
        <TargetPicker
          connections={connections}
          value={target}
          onChange={setTarget}
          noneLabel={t('ai.assignments.noAi')}
          label={t('ai.assignments.person')}
        />
        <div>
          <Button size="sm" disabled={!person || set.isPending} onClick={add}>
            {t('ai.assignments.addPerson')}
          </Button>
        </div>
        <SaveError error={set.error} />
      </div>
    </section>
  )
}
