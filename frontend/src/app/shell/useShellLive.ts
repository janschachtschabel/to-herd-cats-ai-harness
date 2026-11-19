import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useActivityCount } from '@/features/activity/queries'
import { useSessionAttention } from '@/features/auth/useSessionAttention'
import { useLiveUpdates } from '@/features/messaging/live'
import { badgeCount } from '@/lib/format'

/** This tab's live updates, the unread count in the window title ("(3) Herd") and
 *  whether the person attends the tab (the session's idle limit). */
export function useShellLive(): void {
  const { t } = useTranslation()
  const count = useActivityCount()
  useLiveUpdates()
  useSessionAttention()
  useEffect(() => {
    const name = t('app.name')
    document.title = count > 0 ? t('app.titleWithCount', { count: badgeCount(count), name }) : name
  }, [count, t])
}
