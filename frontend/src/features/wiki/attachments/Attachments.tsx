import { Bot, BotOff, Copy, Paperclip, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useSetAttachmentAiLock } from '@/features/ai/lockQueries'
import { AiLockBadge } from '@/features/ai/policy/AiLockBadge'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { ErrorState, LoadMore } from '@/features/shared/states'
import type { Attachment, WikiPage } from '@/lib/api'
import { formatBytes, formatDateTime } from '@/lib/format'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { attachmentMarkdown } from './markdown'
import { useAttachments, useDeleteAttachment, useUploadAttachment } from './queries'

export function Attachments({ page }: { page: WikiPage }) {
  const { t, i18n } = useTranslation()
  const { abilities } = useWiki()
  const aiLock = useSetAttachmentAiLock(page.id)
  const canLockAi = abilities.moderate // governance: `page.moderate`, no `ai.use` needed
  const list = useAttachments(page.id)
  const upload = useUploadAttachment(page.id)
  const remove = useDeleteAttachment(page.id)
  const input = useRef<HTMLInputElement>(null)
  const [deleting, setDeleting] = useState<Attachment | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  async function copy(attachment: Attachment) {
    await navigator.clipboard?.writeText(attachmentMarkdown(attachment))
    setCopied(attachment.id)
  }

  return (
    <section aria-labelledby="attachments-heading" className="mt-10 border-t pt-6">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 id="attachments-heading" className="flex items-center gap-2 text-base font-semibold">
          <Paperclip aria-hidden className="size-4" />
          {t('wiki.attachments.title')}
        </h3>
        {abilities.edit && (
          <>
            <input
              ref={input}
              type="file"
              className="sr-only"
              tabIndex={-1}
              aria-label={t('wiki.attachments.upload')}
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.mutate(file)
                event.target.value = ''
              }}
            />
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              <Upload aria-hidden />
              {upload.isPending ? t('wiki.attachments.uploading') : t('wiki.attachments.upload')}
            </Button>
          </>
        )}
      </div>
      <WikiError error={upload.error} />
      <WikiError error={aiLock.error} />
      {list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : list.isPending ? null : list.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('wiki.attachments.empty')}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {list.items.map((attachment) => (
            <li key={attachment.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
              <a
                href={attachment.url}
                download
                className="min-w-0 flex-1 truncate font-medium hover:underline"
              >
                {attachment.filename}
              </a>
              {attachment.no_ai && <AiLockBadge moderates={canLockAi} />}
              <span className="text-xs text-muted-foreground">
                {formatBytes(attachment.size, i18n.language)} ·{' '}
                {formatDateTime(attachment.created_at, i18n.language)}
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t('wiki.attachments.copyNamed', { name: attachment.filename })}
                onClick={() => void copy(attachment)}
              >
                <Copy aria-hidden />
              </Button>
              {copied === attachment.id && (
                <span role="status" className="text-xs text-muted-foreground">
                  {t('wiki.attachments.copied')}
                </span>
              )}
              {canLockAi && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  disabled={aiLock.isPending}
                  aria-label={t(attachment.no_ai ? 'ai.lock.unlockFile' : 'ai.lock.lockFile', {
                    name: attachment.filename,
                  })}
                  onClick={() => aiLock.mutate(attachment)}
                >
                  {attachment.no_ai ? <Bot aria-hidden /> : <BotOff aria-hidden />}
                </Button>
              )}
              {abilities.edit && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t('wiki.attachments.deleteNamed', { name: attachment.filename })}
                  onClick={() => setDeleting(attachment)}
                >
                  <Trash2 aria-hidden />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
      {abilities.edit && (
        <ConfirmDialog
          open={deleting !== null}
          title={t('wiki.attachments.deleteTitle')}
          text={t('wiki.attachments.deleteText', { name: deleting?.filename ?? '' })}
          confirmLabel={t('actions.delete')}
          destructive
          pending={remove.isPending}
          error={remove.error}
          errorView={<WikiError error={remove.error} />}
          onOpenChange={(open) => !open && setDeleting(null)}
          onConfirm={() =>
            deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })
          }
        />
      )}
    </section>
  )
}
