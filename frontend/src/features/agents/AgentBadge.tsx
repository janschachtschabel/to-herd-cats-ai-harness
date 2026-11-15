import { Bot } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'

/** The mark of everything an agent wrote or is: "KI", with its meaning for screen
 *  readers ("written by an AI" for what it wrote, "an AI agent" beside a name). Shown
 *  to everyone who sees it, AI or not. */
export function AgentBadge({ of = 'text' }: { of?: 'text' | 'agent' }) {
  const { t } = useTranslation()
  const title = of === 'agent' ? t('agents.badge.agent') : t('agents.badge.title')
  return (
    <Badge
      variant="outline"
      className="border-violet-300 bg-violet-50 text-violet-800 dark:border-violet-500/40 dark:bg-violet-500/15 dark:text-violet-200"
      title={title}
    >
      <Bot aria-hidden />
      <span aria-hidden>{t('agents.badge.short')}</span>
      <span className="sr-only">{title}</span>
    </Badge>
  )
}
