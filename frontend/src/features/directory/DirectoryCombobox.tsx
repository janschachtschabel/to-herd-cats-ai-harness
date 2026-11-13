import { Loader2, UserRound, UsersRound } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import type { DirectoryEntry } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { principalKey, useDirectory, type DirectoryType } from './queries'

interface ControlProps {
  id: string
  'aria-invalid'?: boolean
  'aria-describedby'?: string
}

/**
 * A searchable picker for a person or a group (ARIA 1.2 combobox with a listbox popup).
 * Typing searches the directory (debounced); ArrowUp/ArrowDown move, Enter picks,
 * Escape closes. Moving past the last option loads the next page. Typing after a pick
 * clears it (`onSelect(null)`).
 */
export function DirectoryCombobox({
  control,
  selected,
  onSelect,
  exclude,
  type,
  spaceId,
}: {
  control: ControlProps
  selected: DirectoryEntry | null
  onSelect: (entry: DirectoryEntry | null) => void
  exclude: Set<string>
  /** Only people (`user`) or only groups; both when left out. */
  type?: DirectoryType
  /** Only the people who may read this space. */
  spaceId?: string
}) {
  const { t } = useTranslation()
  const listId = useId()
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const q = useDebouncedValue(text.trim())
  const directory = useDirectory(q, exclude, open, type, spaceId)
  // While the typed text has not reached the search yet, older results are not offered.
  const settled = q === text.trim()
  const options = settled ? directory.items : []
  const optionId = (index: number) => `${listId}-option-${index}`
  const shown = selected ? selected.name : text

  const pick = (entry: DirectoryEntry) => {
    onSelect(entry)
    setText('')
    setOpen(false)
    setActive(-1)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) return setOpen(true)
      if (active >= options.length - 1 && directory.hasMore) directory.loadMore()
      setActive((index) => Math.min(index + 1, options.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter' && open) {
      // Enter picks while the list is open; otherwise it submits the form.
      event.preventDefault()
      const entry = options[active]
      if (entry) pick(entry)
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <Input
        {...control}
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && options[active] ? optionId(active) : undefined}
        placeholder={t('directory.placeholder')}
        value={shown}
        onChange={(event) => {
          if (selected) onSelect(null)
          setText(event.target.value)
          setActive(-1)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border bg-popover text-popover-foreground shadow-md">
          <ul id={listId} role="listbox" className="max-h-64 overflow-y-auto p-1">
            {options.map((entry, index) => (
              <li
                key={principalKey(entry)}
                id={optionId(index)}
                role="option"
                aria-selected={index === active}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground"
                // mousedown, not click: the input keeps its focus, so blur does not close first.
                onMouseDown={(event) => {
                  event.preventDefault()
                  pick(entry)
                }}
                onMouseEnter={() => setActive(index)}
              >
                {entry.type === 'group' ? (
                  <UsersRound className="size-4 text-muted-foreground" aria-hidden />
                ) : (
                  <UserRound className="size-4 text-muted-foreground" aria-hidden />
                )}
                <span>{entry.name}</span>
                <span className="sr-only">({t(`principals.${entry.type}`)})</span>
              </li>
            ))}
          </ul>
          <PickerStatus directory={directory} searching={!settled} />
        </div>
      )}
    </div>
  )
}

/** Below the options: searching, failed, nothing found, or more to load. */
function PickerStatus({
  directory: d,
  searching,
}: {
  directory: ReturnType<typeof useDirectory>
  searching: boolean
}) {
  const { t } = useTranslation()
  const base = 'px-3 py-2 text-sm text-muted-foreground'
  if (searching || d.isPending || d.loadingMore) {
    return (
      <p role="status" className={`${base} flex items-center gap-2`}>
        <Loader2 className="size-4 animate-spin" aria-hidden />
        {t('directory.searching')}
      </p>
    )
  }
  if (d.isError) {
    return (
      <p role="alert" className="px-3 py-2 text-sm text-destructive">
        {errorMessage(t, d.error)}
      </p>
    )
  }
  if (d.items.length === 0) {
    return (
      <p role="status" className={base}>
        {t('directory.empty')}
      </p>
    )
  }
  if (d.hasMore) {
    return (
      <button
        type="button"
        tabIndex={-1}
        className={`${base} w-full text-left underline-offset-2 hover:underline`}
        onMouseDown={(event) => {
          event.preventDefault()
          d.loadMore()
        }}
      >
        {t('directory.loadMore')}
      </button>
    )
  }
  return null
}
