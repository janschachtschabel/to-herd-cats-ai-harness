import { Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'

/** Marks an external agent (plan M8): it works from outside through `/mcp` and answers
 *  nothing here by itself. */
export function ExternalBadge() {
  const { t } = useTranslation()
  return (
    <Badge variant="outline" title={t('agents.external.badgeTitle')}>
      <Globe aria-hidden />
      {t('agents.external.badge')}
    </Badge>
  )
}
