import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useActivityCount } from '@/features/activity/queries'
import { useLiveUpdates } from '@/features/messaging/live'
import { badgeCount } from '@/lib/format'

/** This tab's live updates and the unread count in the window title ("(3) Herd"). */
export function useShellLive(): void {
  const { t } = useTranslation()
  const count = useActivityCount()
  useLiveUpdates()
  useEffect(() => {
    const name = t('app.name')
    document.title = count > 0 ? t('app.titleWithCount', { count: badgeCount(count), name }) : name
  }, [count, t])
}
