import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import type { Schemas } from '@/lib/api'

/** Who wrote a skill (or a version of it); an agent carries the AI mark. */
export function SkillAuthor({ author }: { author: Schemas['SkillAuthorOut'] }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      {t('skills.author', { name: author.name ?? t('skills.unknownAuthor') })}
      {author.type === 'agent' && <AgentBadge />}
    </span>
  )
}
