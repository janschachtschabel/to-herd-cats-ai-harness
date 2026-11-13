import { SendHorizontal } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { DirectoryEntry } from '@/lib/api'
import { cn } from '@/lib/utils'
import { insertMention, mentionsIn, typedMention, type Mentioned } from '../mentions'
import { draftKey, getDraft, setDraft } from './drafts'
import { useConversationView } from './ConversationContext'
import { useMentionCandidates } from './mentionCandidates'
import { MentionPicker } from './MentionPicker'
import { useSendMessage } from './queries'

const MAX_CHARS = 20_000

/**
 * Writes a message in Markdown: Enter sends, Shift+Enter starts a new line. `@` opens
 * the people picker (only people who can see the conversation); a pick inserts `@[Name](user:<id>)` and the id is sent as a
 * mention. What one types stays as this conversation's draft while the tab lives.
 * After sending, the people who were mentioned but not told are named.
 */
export function Composer({
  conversationId,
  parentId = null,
  label,
}: {
  conversationId: string
  parentId?: string | null
  label: string
}) {
  const { t } = useTranslation()
  const { conversation, meId } = useConversationView()
  const { send } = useSendMessage(conversationId, parentId)
  const key = draftKey(conversationId, parentId)
  const [text, setTextState] = useState(() => getDraft(key))
  const [caret, setCaret] = useState(text.length)
  const [dismissed, setDismissed] = useState<number | null>(null)
  const [active, setActive] = useState(0)
  const [notNotified, setNotNotified] = useState<Mentioned[]>([])
  const area = useRef<HTMLTextAreaElement>(null)
  const listId = useId()
  const hintId = useId()

  const typing = typedMention(text, caret)
  const pickerOpen = typing !== null && dismissed !== typing.start
  const people = useMentionCandidates(conversation, typing?.query ?? '', pickerOpen, meId)
  const options = pickerOpen ? people.items : []
  const tooLong = text.length > MAX_CHARS

  const setText = (value: string, at: number) => {
    setTextState(value)
    setDraft(key, value)
    setCaret(at)
    setActive(0)
  }

  // After a pick the caret goes behind the inserted mention, once the text is in.
  const placeCaret = useRef<number | null>(null)
  useLayoutEffect(() => {
    const at = placeCaret.current
    if (at === null || !area.current) return
    placeCaret.current = null
    area.current.focus()
    area.current.setSelectionRange(at, at)
  }, [text])

  const pick = (entry: DirectoryEntry) => {
    if (!typing) return
    const next = insertMention(text, typing.start, caret, entry)
    placeCaret.current = next.caret
    setText(next.text, next.caret)
  }

  const submit = async () => {
    const body = text.trim()
    if (!body || tooLong) return
    const mentioned = mentionsIn(body)
    setText('', 0)
    setNotNotified([])
    const written = await send(
      body,
      mentioned.map((m) => m.id),
    )
    if (written && written.not_notified.length > 0) {
      const missed = new Set(written.not_notified.map((id) => id.toLowerCase()))
      setNotNotified(mentioned.filter((m) => missed.has(m.id)))
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return
    if (pickerOpen && options.length > 0) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const step = event.key === 'ArrowDown' ? 1 : -1
        setActive((i) => (i + step + options.length) % options.length)
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        const entry = options[active]
        if (entry) pick(entry)
        return
      }
    }
    if (pickerOpen && event.key === 'Escape') {
      event.preventDefault()
      setDismissed(typing.start)
      return
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submit()
    }
  }

  return (
    <div className="relative border-t pt-2">
      {pickerOpen && (
        <MentionPicker
          id={listId}
          people={people}
          options={options}
          active={active}
          onPick={pick}
          onHover={setActive}
        />
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={area}
          // A combobox while typing "@name": the people list is its popup.
          role="combobox"
          aria-expanded={pickerOpen}
          aria-autocomplete="list"
          aria-label={label}
          aria-describedby={hintId}
          aria-controls={pickerOpen ? listId : undefined}
          aria-activedescendant={pickerOpen && options[active] ? `${listId}-${active}` : undefined}
          aria-invalid={tooLong || undefined}
          value={text}
          rows={Math.min(8, Math.max(1, text.split('\n').length))}
          placeholder={label}
          className={cn(
            'max-h-48 min-h-9 flex-1 resize-none rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50',
            tooLong && 'border-destructive',
          )}
          onChange={(event) => {
            setDismissed(null)
            setText(event.target.value, event.target.selectionStart)
          }}
          onSelect={(event) => setCaret(event.currentTarget.selectionStart)}
          onKeyDown={onKeyDown}
        />
        <Button
          size="icon"
          aria-label={t('messaging.composer.send')}
          disabled={text.trim() === '' || tooLong}
          onClick={() => void submit()}
        >
          <SendHorizontal aria-hidden />
        </Button>
      </div>
      <p id={hintId} className="mt-1 text-xs text-muted-foreground">
        {tooLong
          ? t('messaging.composer.tooLong', { count: MAX_CHARS })
          : t('messaging.composer.hint')}
      </p>
      {notNotified.length > 0 && (
        <p role="status" className="mt-1 text-xs text-amber-700 dark:text-amber-400">
          {t('messaging.composer.notNotified', {
            count: notNotified.length,
            names: notNotified.map((m) => m.name).join(', '),
          })}
        </p>
      )}
    </div>
  )
}
