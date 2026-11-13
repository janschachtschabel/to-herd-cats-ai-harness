import { useTranslation } from 'react-i18next'
import type * as Y from 'yjs'
import { MAX_TABLE_CELLS } from '@collab/cells.mjs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { blockStart, type Unsaveable } from './unsaveable'

/** The latest state cannot be saved: the kind of cause and the block, as far as the
 *  save check knows them; the session goes on. */
export function UnsaveableNotice({ notice, doc }: { notice: Unsaveable; doc: Y.Doc }) {
  const { t, i18n } = useTranslation()
  const start = notice.block === null ? '' : blockStart(doc, notice.block)
  return (
    <Alert variant="destructive">
      <AlertDescription className="flex flex-col gap-1 text-foreground">
        <p>
          {t(`wiki.live.unsaveable.${notice.kind}`, {
            cells: MAX_TABLE_CELLS.toLocaleString(i18n.language),
          })}
        </p>
        {notice.block !== null && (
          <p>
            {t(
              `wiki.live.unsaveable.${notice.through === null ? 'where' : 'wherePair'}${start ? '' : 'Empty'}`,
              {
                number: notice.block + 1,
                next: (notice.through ?? notice.block) + 1,
                start,
              },
            )}
          </p>
        )}
        <p>{t('wiki.live.unsaveable.rest')}</p>
      </AlertDescription>
    </Alert>
  )
}
