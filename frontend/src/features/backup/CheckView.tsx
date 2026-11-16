import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatBytes, formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { codeText } from './codes'
import type { ArchiveCheck, ArchiveFigures } from './queries'

type Row = [label: string, archive: string, here: string]

function rows(
  t: (key: string, options?: Record<string, unknown>) => string,
  locale: string,
  archive: ArchiveFigures,
  here: ArchiveFigures,
): Row[] {
  const number = (n: number) => new Intl.NumberFormat(locale).format(n)
  const files = (f: ArchiveFigures) =>
    t('backup.check.fileCount', { count: f.files, size: formatBytes(f.file_bytes, locale) })
  return [
    [t('backup.check.appVersion'), archive.app_version, here.app_version],
    [t('backup.check.revision'), archive.alembic_revision, here.alembic_revision],
    [t('backup.check.server'), String(archive.server_major), String(here.server_major)],
    [t('backup.check.tools'), String(archive.tools_major ?? '–'), String(here.tools_major ?? '–')],
    [t('backup.check.storage'), archive.storage, here.storage],
    [t('backup.check.tables'), number(archive.tables), number(here.tables)],
    [t('backup.check.rows'), number(archive.rows), number(here.rows)],
    [t('backup.check.files'), files(archive), files(here)],
  ]
}

/** An archive against this installation: figures side by side, the key, what blocks
 *  restoring and the notes. Restoring is offered only when nothing blocks it. */
export function CheckView({ check, onReplace }: { check: ArchiveCheck; onReplace: () => void }) {
  const { t, i18n } = useTranslation()
  const keyBlocks = check.key === 'mismatch' || check.key === 'missing'
  return (
    <section aria-labelledby="backup-check" className="mt-6 rounded-lg border p-4">
      <h3 id="backup-check" className="font-semibold">
        {t('backup.check.title', { name: check.archive_name })}
      </h3>
      {check.created_at && (
        <p className="text-sm text-muted-foreground">
          {t('backup.check.createdAt', { at: formatDateTime(check.created_at, i18n.language) })}
        </p>
      )}
      {check.archive && check.installation && (
        <Table className="mt-3">
          <TableHeader>
            <TableRow>
              <TableHead>{t('backup.check.what')}</TableHead>
              <TableHead>{t('backup.check.archive')}</TableHead>
              <TableHead>{t('backup.check.installation')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows(t, i18n.language, check.archive, check.installation).map(([label, a, b]) => (
              <TableRow key={label}>
                <TableCell className="font-medium">{label}</TableCell>
                <TableCell className={cn('font-mono text-xs break-all', a !== b && 'font-bold')}>
                  {a}
                </TableCell>
                <TableCell className="font-mono text-xs break-all">{b}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell className="font-medium">{t('backup.check.key')}</TableCell>
              <TableCell colSpan={2} className={cn(keyBlocks && 'font-medium text-destructive')}>
                {check.key ? t(`backup.check.keys.${check.key}`) : '–'}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
      {check.problems.length > 0 && (
        <Alert variant="destructive" className="mt-4">
          <AlertTitle>{t('backup.check.problems')}</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {check.problems.map((code: string) => (
                <li key={code}>{codeText(t, code)}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {check.warnings.length > 0 && (
        <Alert className="mt-4">
          <AlertTitle>{t('backup.check.warnings')}</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {check.warnings.map((code: string) => (
                <li key={code}>{codeText(t, code)}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm" role="status">
          {keyBlocks
            ? t('backup.check.keyBlocked')
            : check.can_replace
              ? t('backup.check.fine')
              : t('backup.check.blocked')}
        </p>
        <Button variant="destructive" disabled={!check.can_replace} onClick={onReplace}>
          {t('backup.check.replace')}
        </Button>
      </div>
    </section>
  )
}
