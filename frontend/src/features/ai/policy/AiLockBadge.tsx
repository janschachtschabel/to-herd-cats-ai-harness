import { BotOff } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useMe } from '@/features/auth/queries'
import { seesAiSettings } from '../display'

/** "Locked for AI" on a page or file, shown to people who see AI settings and to
 *  those who may set the lock (`moderates`), with or without AI of their own. */
export function AiLockBadge({ moderates }: { moderates: boolean }) {
  const { t } = useTranslation()
  const sees = seesAiSettings(useMe())
  if (!sees && !moderates) return null
  return (
    <Badge variant="outline">
      <BotOff aria-hidden />
      {t('ai.lock.locked')}
    </Badge>
  )
}
