import { Hourglass } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'

/** A ticket given to an external agent and still open (`awaiting_pickup`, plan M8): it
 *  waits for the agent to pick it up through MCP; nothing runs in the system. */
export function PickupBadge() {
  const { t } = useTranslation()
  return (
    <Badge
      variant="outline"
      className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
      title={t('tickets.pickup.title')}
    >
      <Hourglass aria-hidden />
      {t('tickets.pickup.badge')}
    </Badge>
  )
}
