import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { spaceTagsQuery } from '@/features/wiki/tags/queries'
import type { Space } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { CATEGORIES, KINDS, PRIORITIES } from './display'
import { SORTS, type TicketSearch } from './filters'

/** The list's filters; every change goes into the address (`onChange`). Tags are
 *  offered once a space is chosen (its own and the system-wide ones). */
export function TicketFilters({
  search,
  spaces,
  onChange,
}: {
  search: TicketSearch
  spaces: Space[]
  onChange: (next: TicketSearch) => void
}) {
  const { t } = useTranslation()
  const [text, setText] = useState(search.q ?? '')
  const q = useDebouncedValue(text.trim(), 300)
  const tags = useQuery({ ...spaceTagsQuery(search.space ?? ''), enabled: !!search.space })
  // The typed text goes into the address once it rests; the selects change at once.
  const latest = useRef({ search, onChange })
  useEffect(() => {
    latest.current = { search, onChange }
  })
  useEffect(() => {
    const { search: current, onChange: change } = latest.current
    if ((current.q ?? '') !== q) change({ ...current, q: q || undefined })
  }, [q])

  const set = <K extends keyof TicketSearch>(key: K, value: string) =>
    onChange({ ...search, [key]: value === '' ? undefined : value })

  const select = (
    label: string,
    key: keyof TicketSearch,
    options: { value: string; label: string }[],
    empty: string | null,
  ) => (
    <label className="flex min-w-36 flex-1 flex-col gap-1 text-xs text-muted-foreground">
      {label}
      <NativeSelect
        value={(search[key] as string | undefined) ?? ''}
        onChange={(e) => set(key, e.target.value)}
      >
        {empty !== null && <option value="">{empty}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </NativeSelect>
    </label>
  )

  return (
    <div className="mb-4 flex flex-col gap-3" role="search" aria-label={t('tickets.filters.label')}>
      <Input
        type="search"
        aria-label={t('tickets.filters.text')}
        placeholder={t('tickets.filters.text')}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <div className="flex flex-wrap gap-3">
        {select(
          t('tickets.filters.state'),
          'state',
          [
            { value: 'all', label: t('tickets.filters.allStates') },
            ...CATEGORIES.map((c) => ({ value: c, label: t(`tickets.categories.${c}`) })),
          ],
          t('tickets.filters.unfinished'),
        )}
        {select(
          t('tickets.filters.space'),
          'space',
          spaces.map((s) => ({ value: s.id, label: s.name })),
          t('tickets.filters.allSpaces'),
        )}
        {select(
          t('tickets.fields.kind'),
          'kind',
          KINDS.map((k) => ({ value: k, label: t(`tickets.kinds.${k}`) })),
          t('tickets.filters.any'),
        )}
        {select(
          t('tickets.fields.priority'),
          'priority',
          PRIORITIES.map((p) => ({ value: p, label: t(`tickets.priorities.${p}`) })),
          t('tickets.filters.any'),
        )}
        {search.space &&
          select(
            t('tickets.fields.tags'),
            'tag',
            (tags.data ?? []).map((tag) => ({ value: tag.id, label: tag.name })),
            t('tickets.filters.any'),
          )}
        {select(
          t('tickets.filters.sort'),
          'sort',
          SORTS.map((s) => ({ value: s, label: t(`tickets.sorts.${s}`) })),
          null,
        )}
      </div>
    </div>
  )
}
