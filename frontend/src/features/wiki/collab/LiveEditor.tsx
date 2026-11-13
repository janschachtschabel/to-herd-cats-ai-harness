import { Link, useNavigate } from '@tanstack/react-router'
import { Check, Copy } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { WikiPage } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useLeaveGuard } from '../editor/useLeaveGuard'
import { useFetchLatestPage, useRefreshPage } from '../queries'
import { useWiki } from '../WikiContext'
import type { Connect } from './connect'
import { LiveSurface } from './LiveSurface'
import { Presence } from './Presence'
import { FINAL_STOPS, MARKDOWN_STOPS } from './liveSession'
import { useLiveSession } from './useLiveSession'

const STATUS_STYLE = {
  connecting: 'bg-muted text-muted-foreground',
  synced: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300',
  saving: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
  offline: 'bg-destructive/10 text-destructive',
} as const

/** "Gemeinsam bearbeiten": the visual editor on the page's live session, the people
 *  in it and the connection state. When the session ends for good the text stays
 *  read-only and can be copied as Markdown. */
export function LiveEditor({ page, connect }: { page: WikiPage; connect?: Connect }) {
  const { t } = useTranslation()
  const { space, me } = useWiki()
  const fetchLatest = useFetchLatestPage()
  const live = useLiveSession(page, () => fetchLatest(page), connect)
  const [copied, setCopied] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [notSaved, setNotSaved] = useState(false)
  const navigate = useNavigate()
  const refreshPage = useRefreshPage()
  // Leaving the editor shows the server's state: live saves bypass the page cache.
  const latest = useRef(page)
  useEffect(() => {
    latest.current = page
  })
  useEffect(() => () => refreshPage(latest.current), [refreshPage])
  const editable = live.stopped === null && live.status !== 'connecting'
  const lost = live.lost && live.lost !== page.content_md.trim() ? live.lost : null
  // Once stopped, nothing more reaches the server: only text that differs from the
  // page is at stake (not the editor's own empty paragraph of a refused session).
  const unsaved = live.stopped === null ? live.unsynced > 0 : !!lost && !copied
  useLeaveGuard(unsaved, t('wiki.live.leaveConfirm'))

  async function done() {
    setFinishing(true)
    const saved = await live.finish()
    setFinishing(false)
    setNotSaved(!saved)
    if (saved) {
      await navigate({
        to: '/spaces/$spaceId/p/$',
        params: { spaceId: space.id, _splat: page.path },
      })
    }
  }

  async function copy() {
    if (!lost) return
    await navigator.clipboard?.writeText(lost)
    setCopied(true)
  }

  return (
    <section aria-labelledby="live-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <h2 id="live-heading" className="truncate text-xl font-semibold tracking-tight">
            {page.title}
          </h2>
          <span
            role="status"
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              STATUS_STYLE[live.status],
            )}
          >
            {live.stopped ? t('wiki.live.status.stopped') : t(`wiki.live.status.${live.status}`)}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Presence peers={live.peers} />
          <Button variant="outline" disabled={finishing} onClick={() => void done()}>
            <Check aria-hidden />
            {t('wiki.live.done')}
          </Button>
        </div>
      </div>
      {notSaved && !live.stopped && (
        <Alert variant="destructive">
          <AlertDescription className="text-foreground">{t('wiki.live.notSaved')}</AlertDescription>
        </Alert>
      )}
      {(live.stopped || live.regenerated) && (
        <Alert variant={live.stopped ? 'destructive' : 'default'}>
          <AlertDescription className="flex flex-col gap-2 text-foreground">
            <p>{live.stopped ? t(`wiki.live.stop.${live.stopped}`) : t('wiki.live.regenerated')}</p>
            <div className="flex flex-wrap gap-2">
              {lost && (
                <Button size="sm" variant="outline" onClick={() => void copy()}>
                  <Copy aria-hidden />
                  {copied ? t('wiki.live.copied') : t('wiki.live.copy')}
                </Button>
              )}
              {live.stopped && !FINAL_STOPS.has(live.stopped) && (
                <Button size="sm" variant="outline" onClick={live.retry}>
                  {t('wiki.live.reload')}
                </Button>
              )}
              {live.stopped && MARKDOWN_STOPS.has(live.stopped) && (
                <Button size="sm" variant="outline" asChild>
                  <Link
                    to="/spaces/$spaceId/p/$"
                    params={{ spaceId: space.id, _splat: page.path }}
                    search={{ view: 'edit' }}
                  >
                    {t('wiki.live.markdownEditor')}
                  </Link>
                </Button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}
      <LiveSurface
        key={live.doc.guid}
        doc={live.doc}
        connection={live.connection}
        editable={editable}
        label={t('wiki.live.label', { title: page.title })}
        userName={me?.user.name ?? ''}
        onContentError={() => live.refuse('invalid_content')}
      />
      <p className="text-xs text-muted-foreground">{t('wiki.live.hint')}</p>
    </section>
  )
}
