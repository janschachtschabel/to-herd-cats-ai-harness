import { MessageSquare, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { AnswerSources } from '@/features/agents/AnswerSources'
import { RUN_STOPPED } from '@/features/agents/display'
import { RunStoppedNotice } from '@/features/agents/RunStoppedNotice'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { TicketCards } from '@/features/tickets/TicketCard'
import type { Message } from '@/lib/api'
import { cn } from '@/lib/utils'
import { messageAbilities } from '../abilities'
import { systemText } from '../display'
import { MessageMarkdown } from '../MessageMarkdown'
import { useConversationView } from './ConversationContext'
import { EditMessageForm } from './EditMessageForm'
import { useDeleteMessage, useToggleReaction } from './queries'
import { AddReaction, Reactions } from './Reactions'
import { MessageTime } from './MessageTime'

/** A system entry of a page or ticket thread: a grey line on the timeline. */
function SystemRow({ message }: { message: Message }) {
  const { t, i18n } = useTranslation()
  if (!message.system) return null
  return (
    <div
      className="flex items-center gap-2 py-1 pl-2 text-xs text-muted-foreground"
      data-kind="system"
    >
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-muted-foreground/60" />
      <span>{systemText(t, message.system, i18n.language)}</span>
      <MessageTime iso={message.created_at} />
    </div>
  )
}

/** One message: who, when, the text, reactions, its thread, and what one may do. An
 *  agent's answer carries the AI mark; a stopped run leaves a notice with its reason. */
export function MessageItem({ message }: { message: Message }) {
  if (message.kind === 'system' && message.system?.key === RUN_STOPPED) {
    return <RunStoppedNotice message={message} />
  }
  if (message.kind === 'system') return <SystemRow message={message} />
  return <HumanMessage message={message} />
}

function HumanMessage({ message }: { message: Message }) {
  const { t } = useTranslation()
  const { abilities, meId, openThread, highlight } = useConversationView()
  const can = messageAbilities(message, abilities, meId)
  const toggle = useToggleReaction(message)
  const remove = useDeleteMessage(message)
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const author = message.author?.name ?? t('messaging.message.unknownAuthor')
  const replies = !message.parent_id && openThread ? openThread : null

  return (
    <article
      id={`message-${message.id}`}
      aria-label={t('messaging.message.label', { author })}
      className={cn(
        'group relative rounded-md px-2 py-1.5 hover:bg-muted/40 focus-within:bg-muted/40',
        highlight === message.id && 'bg-amber-100/60 dark:bg-amber-500/15',
      )}
    >
      <header className="flex items-baseline gap-2">
        <span className="text-sm font-semibold">{author}</span>
        {message.kind === 'agent' && <AgentBadge />}
        <MessageTime iso={message.created_at} />
        {message.edited_at && !message.deleted_at && (
          <span className="text-xs text-muted-foreground">{t('messaging.message.edited')}</span>
        )}
      </header>
      {message.deleted_at ? (
        <p className="text-sm text-muted-foreground italic">{t('messaging.message.deleted')}</p>
      ) : editing ? (
        <EditMessageForm message={message} onDone={() => setEditing(false)} />
      ) : (
        <>
          <MessageMarkdown markdown={message.body_md} meId={meId} />
          <TicketCards markdown={message.body_md} />
          {message.kind === 'agent' && (message.run_id ?? message.client_id) && (
            <AnswerSources runId={(message.run_id ?? message.client_id) as string} />
          )}
        </>
      )}
      <Reactions message={message} canReact={can.react} toggle={toggle} />
      {replies && message.reply_count > 0 && (
        <Button
          variant="link"
          size="xs"
          className="px-0"
          onClick={() => replies(message.id)}
          aria-label={t('messaging.thread.openWithCount', { count: message.reply_count, author })}
        >
          {t('messaging.thread.replies', { count: message.reply_count })}
        </Button>
      )}
      {!editing && (
        <div className="absolute top-1 right-1 flex gap-0.5 rounded-md border bg-background p-0.5 opacity-0 shadow-sm group-focus-within:opacity-100 group-hover:opacity-100 has-[[aria-expanded=true]]:opacity-100">
          {can.react && <AddReaction toggle={toggle} />}
          {replies && abilities.post && !message.deleted_at && (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t('messaging.thread.reply')}
              onClick={() => replies(message.id)}
            >
              <MessageSquare aria-hidden />
            </Button>
          )}
          {can.edit && (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t('messaging.message.edit')}
              onClick={() => setEditing(true)}
            >
              <Pencil aria-hidden />
            </Button>
          )}
          {can.remove && (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t('messaging.message.delete')}
              onClick={() => setConfirming(true)}
            >
              <Trash2 aria-hidden />
            </Button>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirming}
        title={t('messaging.message.deleteTitle')}
        text={t('messaging.message.deleteText')}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => remove.mutate(undefined, { onSuccess: () => setConfirming(false) })}
        onOpenChange={setConfirming}
      />
    </article>
  )
}
