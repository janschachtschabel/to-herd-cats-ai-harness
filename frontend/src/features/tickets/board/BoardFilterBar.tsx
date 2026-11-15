import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import { spaceTagsQuery } from '@/features/wiki/tags/queries'
import type { Sprint } from '@/lib/api'
import { KINDS, type TicketKind } from '../display'
import { useEpics } from '../epics/queries'
import { SprintOption } from '../sprints/SprintOption'
import type { BoardFilters } from './queries'

/** Narrows the board: only mine, one kind, one tag, one epic (and what is under it),
 *  one sprint or the backlog; and switches to the daily view (a row per person). */
export function BoardFilterBar({
  spaceId,
  filters,
  onChange,
  sprint,
  sprints,
  grouped,
  onGrouped,
}: {
  spaceId: string
  filters: BoardFilters
  onChange: (next: BoardFilters) => void
  /** The sprint shown (`undefined`: every ticket). */
  sprint: string | undefined
  sprints: Sprint[]
  grouped: boolean
  onGrouped: (grouped: boolean) => void
}) {
  const { t } = useTranslation()
  const tags = useQuery(spaceTagsQuery(spaceId))
  const epics = useEpics(spaceId)
  const label = 'flex min-w-36 flex-1 flex-col gap-1 text-xs text-muted-foreground sm:flex-none'
  return (
    <div
      className="flex flex-wrap items-end gap-3"
      role="search"
      aria-label={t('tickets.board.filters')}
    >
      <label className="flex items-center gap-2 pb-1.5 text-sm">
        <input
          type="checkbox"
          className="accent-primary"
          checked={grouped}
          onChange={(e) => onGrouped(e.target.checked)}
        />
        {t('tickets.daily.group')}
      </label>
      <label className="flex items-center gap-2 pb-1.5 text-sm">
        <input
          type="checkbox"
          className="accent-primary"
          checked={filters.assignee === 'me'}
          onChange={(e) => onChange({ ...filters, assignee: e.target.checked ? 'me' : undefined })}
        />
        {t('tickets.board.onlyMine')}
      </label>
      <label className={label}>
        {t('tickets.daily.sprint')}
        <NativeSelect
          value={sprint === undefined || sprint === 'all' ? '' : sprint}
          onChange={(e) => onChange({ ...filters, sprint: e.target.value || 'all' })}
        >
          <option value="">{t('tickets.daily.allSprints')}</option>
          {sprints.map((s) => (
            <SprintOption key={s.id} sprint={s} />
          ))}
          <option value="none">{t('tickets.daily.backlog')}</option>
        </NativeSelect>
      </label>
      <label className={label}>
        {t('tickets.fields.kind')}
        <NativeSelect
          value={filters.kind ?? ''}
          onChange={(e) =>
            onChange({ ...filters, kind: (e.target.value || undefined) as TicketKind })
          }
        >
          <option value="">{t('tickets.filters.any')}</option>
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`tickets.kinds.${kind}`)}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label className={label}>
        {t('tickets.fields.tags')}
        <NativeSelect
          value={filters.tag ?? ''}
          onChange={(e) => onChange({ ...filters, tag: e.target.value || undefined })}
        >
          <option value="">{t('tickets.filters.any')}</option>
          {(tags.data ?? []).map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </NativeSelect>
      </label>
      <label className={label}>
        {t('tickets.board.epic')}
        <NativeSelect
          value={filters.epic ?? ''}
          onChange={(e) => onChange({ ...filters, epic: e.target.value || undefined })}
        >
          <option value="">{t('tickets.filters.any')}</option>
          {epics.items.map((epic) => (
            <option key={epic.id} value={epic.id}>
              {`${epic.key} ${epic.title}`}
            </option>
          ))}
        </NativeSelect>
      </label>
    </div>
  )
}
