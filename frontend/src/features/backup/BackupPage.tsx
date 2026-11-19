import { DatabaseBackup, FolderDown } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { ArchivesSection } from './ArchivesSection'
import { CheckView } from './CheckView'
import { useBackupRuns, useCheckArchive, useStartBackup } from './queries'
import { ReplaceDialog } from './ReplaceDialog'
import { RestoreNotice } from './RestoreNotice'
import { RunsTable } from './RunsTable'

/** Backups of the whole installation (plan M9 task 13, `backup.manage`: owners only):
 *  the backups with "Jetzt sichern", the archives with download, upload and check, and
 *  restoring an archive in place of everything. The lists follow `backup.changed`. */
export function BackupPage() {
  const { t } = useTranslation()
  const runs = useBackupRuns()
  const start = useStartBackup()
  const check = useCheckArchive()
  const [checking, setChecking] = useState<string | null>(null)
  const [replacing, setReplacing] = useState<string | null>(null)
  const [started, setStarted] = useState(false)

  const onCheck = (name: string) => {
    setChecking(name)
    check.mutate(name)
  }

  return (
    <div>
      <PageHeader
        title={t('backup.title')}
        description={t('backup.description')}
        actions={
          <Button disabled={start.isPending} onClick={() => start.mutate()}>
            <DatabaseBackup aria-hidden />
            {start.isPending ? t('backup.starting') : t('backup.start')}
          </Button>
        }
      />
      <RestoreNotice started={started} />
      {start.isError && <SaveError error={start.error} />}

      <section aria-labelledby="backup-runs">
        <h2 id="backup-runs" className="mb-3 text-lg font-semibold">
          {t('backup.runs.title')}
        </h2>
        {runs.isPending ? (
          <LoadingState rows={3} />
        ) : runs.isError ? (
          <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
        ) : runs.items.length === 0 ? (
          <EmptyState text={t('backup.runs.empty')} />
        ) : (
          <RunsTable runs={runs.items} />
        )}
        <LoadMore hasMore={runs.hasMore} loading={runs.loadingMore} onLoad={runs.loadMore} />
      </section>

      <ArchivesSection checking={checking} onCheck={onCheck} />
      {checking && check.isPending && (
        <p className="mt-6 text-sm text-muted-foreground" role="status">
          {t('backup.check.checking')}
        </p>
      )}
      {check.isError && <ErrorState error={check.error} />}
      {check.data && !check.isPending && (
        <CheckView check={check.data} onReplace={() => setReplacing(check.data.archive_name)} />
      )}

      <aside className="mt-10 flex gap-3 rounded-lg border bg-muted/40 p-4 text-sm">
        <FolderDown className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div>
          <h2 className="font-medium">{t('backup.export.title')}</h2>
          <p className="text-muted-foreground">{t('backup.export.text')}</p>
        </div>
      </aside>

      <ReplaceDialog
        archive={replacing}
        onOpenChange={(open) => !open && setReplacing(null)}
        onStarted={() => setStarted(true)}
      />
    </div>
  )
}
