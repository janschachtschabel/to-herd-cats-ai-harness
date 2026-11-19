import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatBytes, formatDateTime } from '@/lib/format'
import { codeText } from './codes'
import type { BackupRun } from './queries'

const STATE_VARIANT = {
  running: 'secondary',
  ok: 'outline',
  failed: 'destructive',
  interrupted: 'destructive',
} as const

/** The backups, newest first: when, why, how it went, the archive and its copy. */
export function RunsTable({ runs }: { runs: BackupRun[] }) {
  const { t, i18n } = useTranslation()
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('backup.runs.started')}</TableHead>
          <TableHead>{t('backup.runs.trigger')}</TableHead>
          <TableHead>{t('backup.runs.state')}</TableHead>
          <TableHead className="text-right">{t('backup.runs.size')}</TableHead>
          <TableHead>{t('backup.runs.archive')}</TableHead>
          <TableHead>{t('backup.runs.offsite')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => {
          const waiting = run.state === 'running' && run.trigger === 'admin' && !run.archive
          return (
            <TableRow key={run.id}>
              <TableCell className="whitespace-nowrap">
                {formatDateTime(run.started_at, i18n.language)}
              </TableCell>
              <TableCell>{t(`backup.triggers.${run.trigger}`)}</TableCell>
              <TableCell>
                <Badge variant={STATE_VARIANT[run.state]}>{t(`backup.states.${run.state}`)}</Badge>
                {run.error_code && (
                  <p className="mt-1 text-xs text-destructive">{codeText(t, run.error_code)}</p>
                )}
                {waiting && (
                  <p className="mt-1 text-xs text-muted-foreground">{t('backup.runs.waiting')}</p>
                )}
              </TableCell>
              <TableCell className="text-right whitespace-nowrap">
                {run.bytes != null ? formatBytes(run.bytes, i18n.language) : '–'}
              </TableCell>
              <TableCell className="font-mono text-xs break-all">{run.archive ?? '–'}</TableCell>
              <TableCell>{t(`backup.offsite.${run.offsite_state}`)}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
