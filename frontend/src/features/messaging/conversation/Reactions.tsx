import { SmilePlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Message } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import type { useToggleReaction } from './queries'

type Toggle = ReturnType<typeof useToggleReaction>

const QUICK_EMOJI = ['👍', '❤️', '😄', '🎉', '👀', '✅'] as const

/** The reactions under a message; each chip adds or takes back one's own. */
export function Reactions({
  message,
  canReact,
  toggle,
}: {
  message: Message
  canReact: boolean
  toggle: Toggle
}) {
  const { t } = useTranslation()
  if (message.reactions.length === 0 && !toggle.error) return null
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1">
      {message.reactions.map((reaction) => (
        <button
          key={reaction.emoji}
          type="button"
          aria-pressed={reaction.mine}
          disabled={!canReact || toggle.isPending}
          aria-label={t(
            reaction.mine ? 'messaging.reactions.chipMine' : 'messaging.reactions.chip',
            {
              emoji: reaction.emoji,
              count: reaction.count,
            },
          )}
          onClick={() => toggle.mutate(reaction.emoji)}
          className={cn(
            'inline-flex h-6 items-center gap-1 rounded-full border px-2 text-xs',
            reaction.mine ? 'border-primary bg-primary/10' : 'bg-background hover:bg-muted',
          )}
        >
          <span aria-hidden>{reaction.emoji}</span>
          <span aria-hidden className="tabular-nums">
            {reaction.count}
          </span>
        </button>
      ))}
      {toggle.error ? (
        <span role="alert" className="text-xs text-destructive">
          {errorMessage(t, toggle.error)}
        </span>
      ) : null}
    </div>
  )
}

/** The button that adds a reaction (one of a few common ones). */
export function AddReaction({ toggle }: { toggle: Toggle }) {
  const { t } = useTranslation()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-xs" aria-label={t('messaging.reactions.add')}>
          <SmilePlus aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="flex min-w-0 gap-1 p-1">
        {QUICK_EMOJI.map((emoji) => (
          <DropdownMenuItem
            key={emoji}
            className="justify-center px-2 text-base"
            aria-label={t('messaging.reactions.with', { emoji })}
            onSelect={() => toggle.mutate(emoji)}
          >
            {emoji}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
