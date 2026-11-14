import { MessageCircleQuestion } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useMe } from '@/features/auth/queries'
import { RunLink } from '@/features/runs/RunBits'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { formatDateTime } from '@/lib/format'
import { useNow } from '@/lib/useNow'
import { CardFrame, CardState } from './CardFrame'
import { questionView } from './display'
import { useAnswerQuestion, useQuestion, type Question } from './queries'

const MAX_ANSWER = 4000

function AnswerForm({
  question,
  answer,
}: {
  question: Question
  answer: ReturnType<typeof useAnswerQuestion>
}) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const id = useId()
  const tooLong = text.length > MAX_ANSWER
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (!text.trim() || tooLong) return
        answer.mutate({ text: text.trim(), version: question.version })
      }}
    >
      <Label htmlFor={id}>{t('approvals.question.answerLabel')}</Label>
      <Textarea
        id={id}
        value={text}
        rows={3}
        aria-invalid={tooLong || undefined}
        onChange={(event) => setText(event.target.value)}
      />
      {tooLong && (
        <p className="text-xs text-destructive">
          {t('approvals.question.tooLong', { count: MAX_ANSWER })}
        </p>
      )}
      <div>
        <Button type="submit" size="sm" disabled={answer.isPending || !text.trim() || tooLong}>
          {t('approvals.question.send')}
        </Button>
      </div>
    </form>
  )
}

/** An agent's question: the question, its state (waiting, answered, expired), the
 *  answer field for the person asked (the answer shows only to them), a refusal in
 *  words, and a link to the run. */
export function QuestionCardView({ question }: { question: Question }) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const now = useNow(60_000)
  const answer = useAnswerQuestion(question.id)
  const view = questionView(question, now)
  const mine = question.addressed_to === me?.user.id
  return (
    <CardFrame
      icon={<MessageCircleQuestion className="size-4" />}
      label={t('approvals.question.label')}
      title={t('approvals.question.title')}
      state={
        <CardState tone={view === 'pending' ? 'waiting' : view === 'answered' ? 'ok' : 'off'}>
          {t(`approvals.question.state.${view}`)}
        </CardState>
      }
    >
      <p className="whitespace-pre-wrap">{question.question}</p>
      {view === 'pending' && mine && <AnswerForm question={question} answer={answer} />}
      {view === 'pending' && !mine && (
        <p className="text-xs text-muted-foreground">{t('approvals.question.askerAnswers')}</p>
      )}
      {view === 'answered' && (
        <p className="text-xs">
          {t('approvals.question.answeredAt', {
            when: question.answered_at ? formatDateTime(question.answered_at, i18n.language) : '',
          })}
          {question.answer !== null && (
            <span className="mt-0.5 block whitespace-pre-wrap text-muted-foreground">
              {t('approvals.question.yourAnswer', { answer: question.answer })}
            </span>
          )}
        </p>
      )}
      {view === 'expired' && <p className="text-xs">{t('approvals.question.expired')}</p>}
      {answer.isError && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, answer.error)}
        </p>
      )}
      <RunLink runId={question.run_id} />
    </CardFrame>
  )
}

/** A question card by id (a message's card); someone who may not see it reads the
 *  question as the message has it. */
export function QuestionCard({ questionId, text }: { questionId: string; text: string }) {
  const { t } = useTranslation()
  const question = useQuestion(questionId)
  if (question.isPending) {
    return <p className="mt-1 text-xs text-muted-foreground">{t('states.loading')}</p>
  }
  if (question.data) return <QuestionCardView question={question.data} />
  const hidden = question.error instanceof ApiError && question.error.status === 404
  return (
    <CardFrame
      icon={<MessageCircleQuestion className="size-4" />}
      label={t('approvals.question.label')}
      title={t('approvals.question.title')}
    >
      <p className="whitespace-pre-wrap">{text}</p>
      {hidden ? (
        <p className="text-xs text-muted-foreground">{t('approvals.question.askerAnswers')}</p>
      ) : (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, question.error)}
        </p>
      )}
    </CardFrame>
  )
}
