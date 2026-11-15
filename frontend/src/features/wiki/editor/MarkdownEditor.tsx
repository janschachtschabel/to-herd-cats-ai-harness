import { useNavigate } from '@tanstack/react-router'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field } from '@/features/shared/forms'
import { ApiError, type WikiPage } from '@/lib/api'
import { MarkdownContent } from '../MarkdownContent'
import { useFetchLatestPage, useUpdatePage } from '../queries'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { ConflictDialog } from './ConflictDialog'
import { useLeaveGuard } from './useLeaveGuard'

const MAX_CONTENT = 200_000

/** Markdown on the left, the rendered page on the right. Saving sends the version the
 *  edit started from; if someone saved in between (409), the person chooses. Saving
 *  here ends a live session on the page (its editors reconnect to this version). */
export function MarkdownEditor({ page }: { page: WikiPage }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { space, titles } = useWiki()
  const [base, setBase] = useState(page)
  const [title, setTitle] = useState(page.title)
  const [content, setContent] = useState(page.content_md)
  const [summary, setSummary] = useState('')
  const [conflict, setConflict] = useState(false)
  const [rebased, setRebased] = useState(false)
  const [busy, setBusy] = useState(false)
  const update = useUpdatePage(base)
  const fetchLatest = useFetchLatestPage()
  const dirty = title !== base.title || content !== base.content_md
  useLeaveGuard(dirty && !busy, t('wiki.editor.leaveConfirm'))
  const view = () =>
    navigate({ to: '/spaces/$spaceId/p/$', params: { spaceId: space.id, _splat: base.path } })

  function save(event?: FormEvent) {
    event?.preventDefault()
    if (!title.trim() || busy) return
    setBusy(true)
    update.mutate(
      {
        title: title.trim() !== base.title ? title.trim() : undefined,
        content_md: content !== base.content_md ? content : undefined,
        change_summary: summary.trim() || undefined,
        version: base.version,
      },
      {
        onSuccess: (saved) => {
          setBase(saved)
          void view()
        },
        onError: (error) => {
          setBusy(false)
          if (error instanceof ApiError && error.isVersionConflict) setConflict(true)
        },
      },
    )
  }

  async function resolve(keepMine: boolean) {
    setBusy(true)
    try {
      const latest = await fetchLatest(base)
      setBase(latest)
      if (!keepMine) {
        setTitle(latest.title)
        setContent(latest.content_md)
      }
      setRebased(keepMine)
      setConflict(false)
      update.reset()
    } finally {
      setBusy(false)
    }
  }

  function onKeyDown(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key === 's') {
      event.preventDefault()
      save()
    }
  }

  return (
    <form
      onSubmit={save}
      onKeyDown={onKeyDown}
      className="flex flex-col gap-4"
      aria-label={t('wiki.editor.title')}
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-1">
          <Field
            label={t('wiki.fields.title')}
            error={title.trim() ? undefined : t('validation.required')}
          >
            {(props) => (
              <Input
                {...props}
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            )}
          </Field>
        </div>
        <Button type="button" variant="outline" onClick={() => void view()}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={busy || !title.trim()}>
          {t('actions.save')}
        </Button>
      </div>
      {rebased && (
        <Alert>
          <AlertDescription className="text-foreground">
            {t('wiki.editor.rebased')}
          </AlertDescription>
        </Alert>
      )}
      <WikiError
        error={
          update.error instanceof ApiError && update.error.isVersionConflict ? null : update.error
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Field label={t('wiki.editor.markdown')} hint={t('wiki.editor.hint')}>
          {(props) => (
            <Textarea
              {...props}
              className="min-h-[28rem] font-mono text-sm"
              maxLength={MAX_CONTENT}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          )}
        </Field>
        <section
          aria-label={t('wiki.editor.preview')}
          className="min-h-[28rem] rounded-lg border p-4"
        >
          <MarkdownContent spaceId={space.id} markdown={content} lookup={titles} />
        </section>
      </div>
      <Field label={t('wiki.editor.summary')}>
        {(props) => (
          <Input
            {...props}
            maxLength={300}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        )}
      </Field>
      <ConflictDialog
        open={conflict}
        busy={busy}
        onKeepMine={() => void resolve(true)}
        onDiscardMine={() => void resolve(false)}
      />
    </form>
  )
}
