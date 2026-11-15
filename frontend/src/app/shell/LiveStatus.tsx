import { WifiOff } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useLiveStatus } from '@/lib/live'

/** A quiet note in the header while live updates are interrupted. */
export function LiveHint() {
  const { t } = useTranslation()
  const status = useLiveStatus()
  if (status !== 'retrying' && status !== 'limited') return null
  return (
    <p role="status" className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <WifiOff className="size-3.5" aria-hidden />
      {status === 'limited' ? t('live.limited') : t('live.retrying')}
    </p>
  )
}
