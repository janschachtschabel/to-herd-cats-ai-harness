import { UserLock } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'

/** The personal mark of a message (module review M8 2, G2): it holds what the person
 *  read through her own access, or came about where that was in the history. Such a
 *  message is only in her DM alone with the agent. A button that unfolds what it means
 *  (`PersonalNote`). */
export function PersonalBadge({
  open,
  onToggle,
  noteId,
}: {
  open: boolean
  onToggle: () => void
  noteId: string
}) {
  const { t } = useTranslation()
  return (
    <Badge
      asChild
      variant="outline"
      className="cursor-pointer border-sky-300 bg-sky-50 text-sky-800 hover:bg-sky-100 dark:border-sky-500/40 dark:bg-sky-500/15 dark:text-sky-200"
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={noteId}
        title={t('agents.personalMark.title')}
        onClick={onToggle}
      >
        <UserLock aria-hidden />
        {t('agents.personalMark.short')}
      </button>
    </Badge>
  )
}

/** What the personal mark means, under the message's header once its badge is pressed. */
export function PersonalNote({ id }: { id: string }) {
  const { t } = useTranslation()
  return (
    <p id={id} className="mt-0.5 max-w-prose text-xs text-muted-foreground">
      {t('agents.personalMark.text')}
    </p>
  )
}
