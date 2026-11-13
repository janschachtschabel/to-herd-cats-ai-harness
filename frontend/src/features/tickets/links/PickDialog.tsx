import { FileText } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ErrorState } from '@/features/shared/states'
import type { SearchHit, TicketHit } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { cn } from '@/lib/utils'
import { StatusBadge } from '../parts'
import { useFind } from './queries'

type Hit = SearchHit | TicketHit

/** Finds a page or a ticket by its title (a ticket also by its key) and picks it:
 *  Up/Down choose, Enter picks. Only what one may see is found. */
export function PickDialog({
  type,
  open,
  onOpenChange,
  title,
  onPick,
}: {
  type: 'page' | 'ticket'
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  onPick: (hit: Hit) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{t(`tickets.pick.${type}`)}</DialogDescription>
        </DialogHeader>
        {open && <Picker type={type} onPick={onPick} />}
      </DialogContent>
    </Dialog>
  )
}

function Picker({ type, onPick }: { type: 'page' | 'ticket'; onPick: (hit: Hit) => void }) {
  const { t } = useTranslation()
  const listId = useId()
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  const q = useDebouncedValue(text.trim(), 250)
  const found = useFind(type, q)
  const hits = ((found.data ?? []) as Hit[]).filter((hit) => hit.type === type)
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && hits.length) setActive((i) => (i + 1) % hits.length)
    else if (event.key === 'ArrowUp' && hits.length)
      setActive((i) => (i - 1 + hits.length) % hits.length)
    else if (event.key === 'Enter' && hits[active]) onPick(hits[active])
    else return
    event.preventDefault()
  }
  return (
    <div className="flex flex-col gap-3">
      <Input
        role="combobox"
        aria-expanded={hits.length > 0}
        aria-controls={listId}
        aria-activedescendant={hits[active] ? `${listId}-${active}` : undefined}
        aria-autocomplete="list"
        aria-label={t('tickets.pick.input')}
        placeholder={t('tickets.pick.input')}
        autoFocus
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          setActive(0)
        }}
        onKeyDown={onKeyDown}
      />
      {found.isError ? (
        <ErrorState error={found.error} />
      ) : q === '' ? null : hits.length === 0 ? (
        <p role="status" className="text-sm text-muted-foreground">
          {found.isFetching ? t('states.loading') : t('tickets.pick.empty')}
        </p>
      ) : (
        <ul
          id={listId}
          role="listbox"
          aria-label={t('tickets.pick.results')}
          className="flex flex-col gap-1"
        >
          {hits.map((hit, index) => (
            <li
              key={hit.id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                index === active ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/60',
              )}
              onMouseEnter={() => setActive(index)}
              onClick={() => onPick(hit)}
            >
              {hit.type === 'ticket' ? (
                <>
                  <span className="font-mono text-xs text-muted-foreground">{hit.key}</span>
                  <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                  <StatusBadge status={hit.status} />
                </>
              ) : (
                <>
                  <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{hit.space_name}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
