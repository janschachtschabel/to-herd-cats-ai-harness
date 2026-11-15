import { Bot, Loader2, UserRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { ExternalMark } from '@/features/agents/external/ExternalMark'
import type { DirectoryEntry } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import type { MentionCandidates } from './mentionCandidates'

/** The people (and, for people with AI, the space's agents, marked) one can mention, above the composer while `@name` is being typed.
 *  Arrows move, Enter or Tab picks, Escape closes (handled by the composer). */
export function MentionPicker({
  id,
  people,
  options,
  active,
  onPick,
  onHover,
}: {
  id: string
  people: MentionCandidates
  options: DirectoryEntry[]
  active: number
  onPick: (entry: DirectoryEntry) => void
  onHover: (index: number) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="absolute bottom-full left-0 z-40 mb-1 w-72 rounded-lg border bg-popover text-popover-foreground shadow-md">
      <ul id={id} role="listbox" aria-label={t('messaging.mention.label')} className="p-1">
        {options.map((entry, index) => (
          <li
            key={entry.id}
            id={`${id}-${index}`}
            role="option"
            aria-selected={index === active}
            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground"
            onMouseDown={(event) => {
              event.preventDefault() // the composer keeps its focus
              onPick(entry)
            }}
            onMouseEnter={() => onHover(index)}
          >
            {entry.type === 'agent' ? (
              <Bot className="size-4 text-muted-foreground" aria-hidden />
            ) : (
              <UserRound className="size-4 text-muted-foreground" aria-hidden />
            )}
            <span className="min-w-0 flex-1 truncate">{entry.name}</span>
            {entry.type === 'agent' && <AgentBadge of="agent" />}
            {entry.kind === 'external' && <ExternalMark />}
          </li>
        ))}
      </ul>
      {people.isPending ? (
        <p
          role="status"
          className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground"
        >
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {t('directory.searching')}
        </p>
      ) : people.isError ? (
        <p role="alert" className="px-3 py-2 text-xs text-destructive">
          {errorMessage(t, people.error)}
        </p>
      ) : options.length === 0 ? (
        <p role="status" className="px-3 py-2 text-xs text-muted-foreground">
          {t('directory.empty')}
        </p>
      ) : null}
    </div>
  )
}
