import { useTranslation } from 'react-i18next'
import type * as Y from 'yjs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { blockStart, type Unsaveable } from './unsaveable'

/** The latest state cannot be saved: the kind of cause and the block, as far as the
 *  save check knows them; the session goes on. */
export function UnsaveableNotice({ notice, doc }: { notice: Unsaveable; doc: Y.Doc }) {
  const { t } = useTranslation()
  const start = notice.block === null ? '' : blockStart(doc, notice.block)
  return (
    <Alert variant="destructive">
      <AlertDescription className="flex flex-col gap-1 text-foreground">
        <p>{t(`wiki.live.unsaveable.${notice.kind}`)}</p>
        {notice.block !== null && (
          <p>
            {start
              ? t('wiki.live.unsaveable.where', { number: notice.block + 1, start })
              : t('wiki.live.unsaveable.whereEmpty', { number: notice.block + 1 })}
          </p>
        )}
        <p>{t('wiki.live.unsaveable.rest')}</p>
      </AlertDescription>
    </Alert>
  )
}
