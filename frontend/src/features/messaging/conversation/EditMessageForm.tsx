import { useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { Message } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { mentionsIn } from '../mentions'
import { useEditMessage } from './queries'

/** Changes one's own message in place: Enter saves, Shift+Enter breaks the line,
 *  Escape cancels. The mentions follow the text. */
export function EditMessageForm({ message, onDone }: { message: Message; onDone: () => void }) {
  const { t } = useTranslation()
  const edit = useEditMessage(message)
  const [text, setText] = useState(message.body_md)
  const blank = text.trim() === ''

  const save = () => {
    if (blank || edit.isPending) return
    if (text === message.body_md) return onDone()
    edit.mutate(
      { body_md: text, mentions: mentionsIn(text).map((m) => m.id) },
      { onSuccess: onDone },
    )
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      save()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onDone()
    }
  }

  return (
    <div className="mt-1 flex flex-col gap-2">
      <Textarea
        aria-label={t('messaging.message.editLabel')}
        value={text}
        rows={Math.min(8, Math.max(2, text.split('\n').length))}
        autoFocus
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      {edit.error ? (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, edit.error)}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button size="sm" onClick={save} disabled={blank || edit.isPending}>
          {t('actions.save')}
        </Button>
        <Button size="sm" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
      </div>
    </div>
  )
}
