import { Download, SearchCheck, Upload } from 'lucide-react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { SaveError } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatBytes, formatDateTime } from '@/lib/format'
import { archiveDownloadUrl, useArchives, useUploadArchive } from './queries'

/** The archives in the backups directory: download, check, upload one from elsewhere. */
export function ArchivesSection({
  checking,
  onCheck,
}: {
  checking: string | null
  onCheck: (name: string) => void
}) {
  const { t, i18n } = useTranslation()
  const archives = useArchives()
  const upload = useUploadArchive()
  const input = useRef<HTMLInputElement>(null)

  return (
    <section aria-labelledby="backup-archives" className="mt-10">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="backup-archives" className="text-lg font-semibold">
            {t('backup.archives.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('backup.archives.description')}</p>
        </div>
        <Button
          variant="outline"
          disabled={upload.isPending}
          onClick={() => input.current?.click()}
        >
          <Upload aria-hidden />
          {upload.isPending ? t('backup.archives.uploading') : t('backup.archives.upload')}
        </Button>
        <input
          ref={input}
          type="file"
          accept=".tar,application/x-tar"
          aria-label={t('backup.archives.file')}
          className="sr-only"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) upload.mutate(file)
          }}
        />
      </div>
      {upload.isError && <SaveError error={upload.error} />}
      {upload.isSuccess && (
        <p className="mb-3 text-sm" role="status">
          {t('backup.archives.uploaded_done', { name: upload.data.name })}
        </p>
      )}
      {archives.isPending ? (
        <LoadingState rows={2} />
      ) : archives.isError ? (
        <ErrorState error={archives.error} onRetry={() => void archives.refetch()} />
      ) : archives.items.length === 0 ? (
        <EmptyState text={t('backup.archives.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('backup.archives.name')}</TableHead>
              <TableHead>{t('backup.archives.created')}</TableHead>
              <TableHead className="text-right">{t('backup.archives.size')}</TableHead>
              <TableHead>{t('backup.archives.origin')}</TableHead>
              <TableHead>
                <span className="sr-only">{t('common.actions')}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {archives.items.map((archive) => (
              <TableRow key={archive.name}>
                <TableCell className="font-mono text-xs break-all">{archive.name}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {formatDateTime(archive.created_at, i18n.language)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {formatBytes(archive.bytes, i18n.language)}
                </TableCell>
                <TableCell>
                  {archive.uploaded ? t('backup.archives.uploaded') : t('backup.archives.made')}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <Button asChild size="sm" variant="ghost">
                      <a
                        href={archiveDownloadUrl(archive.name)}
                        download
                        aria-label={t('backup.archives.downloadLabel', { name: archive.name })}
                      >
                        <Download aria-hidden />
                        {t('backup.archives.download')}
                      </a>
                    </Button>
                    <Button
                      size="sm"
                      variant={checking === archive.name ? 'secondary' : 'outline'}
                      aria-label={t('backup.archives.checkLabel', { name: archive.name })}
                      onClick={() => onCheck(archive.name)}
                    >
                      <SearchCheck aria-hidden />
                      {t('backup.archives.check')}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore
        hasMore={archives.hasMore}
        loading={archives.loadingMore}
        onLoad={archives.loadMore}
      />
    </section>
  )
}
