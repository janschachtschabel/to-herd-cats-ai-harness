import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { showMaintenance, useMaintenanceState } from '@/features/shared/maintenance'
import { formatDateTime } from '@/lib/format'
import { codeText } from './codes'
import { useRestoreStatus } from './queries'

/** The last attempt to replace the installation. After this tab started one it waits
 *  for maintenance to begin (the safety archive comes first) and then shows the
 *  maintenance page; an attempt that failed before says why. */
export function RestoreNotice({ started }: { started: boolean }) {
  const { t, i18n } = useTranslation()
  const status = useRestoreStatus()
  const attempt = status.data ?? null
  const failed = attempt?.state === 'failed'
  const waiting = started && !failed
  const maintenance = useMaintenanceState(waiting)
  // Only while waiting for this tab's replace, never on an answer cached from before.
  const begun = waiting && maintenance.isFetchedAfterMount && maintenance.data?.active === true
  useEffect(() => {
    if (begun) showMaintenance()
  }, [begun])

  if (failed) {
    const reason = attempt.code ? codeText(t, attempt.code) : t('backup.codes.restore.failed')
    return (
      <Alert variant="destructive" className="mb-6">
        <AlertDescription>
          {t('backup.replace.failed', { name: attempt.archive_name ?? '', reason })}
        </AlertDescription>
      </Alert>
    )
  }
  if (started) {
    return (
      <Alert className="mb-6" role="status">
        <AlertDescription>{t('backup.replace.started')}</AlertDescription>
      </Alert>
    )
  }
  if (attempt?.state === 'requested') {
    return (
      <p className="mb-6 text-sm text-muted-foreground">
        {t('backup.replace.requested', {
          name: attempt.archive_name ?? '',
          at: formatDateTime(attempt.at, i18n.language),
        })}
      </p>
    )
  }
  return null
}
