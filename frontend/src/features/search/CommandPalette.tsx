// Ported-from: to-herd-cats-ai@46352bb:frontend/src/features/search/CommandPalette.tsx
import { useNavigate, useParams } from '@tanstack/react-router'
import { Search } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { ErrorState } from '@/features/shared/states'
import type { SearchHit } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { cn } from '@/lib/utils'
import { Highlight } from './Highlight'
import { useSearch } from './queries'

/** Search over every page one may read: Up/Down choose, Enter opens, Escape closes.
 *  Inside a space, "only this space" narrows the search to it. */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const currentSpace = useParams({ strict: false, select: (p) => p.spaceId ?? null })
  const [text, setText] = useState('')
  const [onlyHere, setOnlyHere] = useState(false)
  const [active, setActive] = useState(0)
  const q = useDebouncedValue(text.trim(), 250)
  const spaceId = onlyHere ? currentSpace : null
  const results = useSearch(q, spaceId)
  const listId = useId()
  const optionId = (i: number) => `${listId}-${i}`

  function openHit(hit: SearchHit) {
    onOpenChange(false)
    void navigate({
      to: '/spaces/$spaceId/p/$',
      params: { spaceId: hit.space_id, _splat: hit.path },
    })
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const count = results.items.length
    if (event.key === 'ArrowDown' && count) setActive((i) => (i + 1) % count)
    else if (event.key === 'ArrowUp' && count) setActive((i) => (i - 1 + count) % count)
    else if (event.key === 'Enter' && results.items[active]) openHit(results.items[active])
    else return
    event.preventDefault()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[15%] translate-y-0 gap-0 p-0 sm:max-w-xl">
        <DialogTitle className="sr-only">{t('search.title')}</DialogTitle>
        <DialogDescription className="sr-only">{t('search.description')}</DialogDescription>
        <div className="flex items-center gap-2 border-b px-3">
          <Search aria-hidden className="size-4 text-muted-foreground" />
          <input
            role="combobox"
            aria-expanded={results.items.length > 0}
            aria-controls={listId}
            aria-activedescendant={results.items.length ? optionId(active) : undefined}
            aria-autocomplete="list"
            aria-label={t('search.input')}
            placeholder={t('search.placeholder')}
            className="h-12 flex-1 bg-transparent text-sm outline-none"
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              setActive(0)
            }}
            onKeyDown={onKeyDown}
            autoFocus
          />
        </div>
        {currentSpace && (
          <label className="flex items-center gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="accent-primary"
              checked={onlyHere}
              onChange={(event) => {
                setOnlyHere(event.target.checked)
                setActive(0)
              }}
            />
            {t('search.onlyHere')}
          </label>
        )}
        <div className="max-h-[60vh] overflow-y-auto p-2">
          {results.isError ? (
            <ErrorState error={results.error} />
          ) : q === '' ? (
            <p className="p-3 text-sm text-muted-foreground">{t('search.hint')}</p>
          ) : results.items.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground" role="status">
              {results.isFetching ? t('states.loading') : t('search.empty')}
            </p>
          ) : (
            <ul
              id={listId}
              role="listbox"
              aria-label={t('search.results')}
              className="flex flex-col gap-1"
            >
              {results.items.map((hit, i) => (
                <li
                  key={hit.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  className={cn(
                    'cursor-pointer rounded-md px-3 py-2 text-sm',
                    i === active ? 'bg-accent' : 'hover:bg-accent/60',
                  )}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => openHit(hit)}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate font-medium">{hit.title}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{hit.space_name}</span>
                  </div>
                  {hit.snippet && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                      <Highlight snippet={hit.snippet} />
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
          {results.hasMore && (
            <div className="flex justify-center p-2">
              <Button variant="outline" size="sm" onClick={results.loadMore}>
                {t('actions.loadMore')}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
