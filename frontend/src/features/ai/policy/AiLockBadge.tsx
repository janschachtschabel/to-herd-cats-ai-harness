import { BotOff } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useMe } from '@/features/auth/queries'
import { seesAiSettings } from '../display'

/** "Locked for AI" on a page or file, shown only to people who see AI settings. */
export function AiLockBadge() {
  const { t } = useTranslation()
  if (!seesAiSettings(useMe())) return null
  return (
    <Badge variant="outline">
      <BotOff aria-hidden />
      {t('ai.lock.locked')}
    </Badge>
  )
}
