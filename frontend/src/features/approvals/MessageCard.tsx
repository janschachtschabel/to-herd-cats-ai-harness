import type { Message } from '@/lib/api'
import { ApprovalCard } from './ApprovalCard'
import { QuestionCard } from './QuestionCard'

/** A run's card in a conversation or thread: a message of kind `approval` or
 *  `question` that names its card (`card.id`); its text is the tool (an approval) or the question. */
export function MessageCard({ message }: { message: Message }) {
  const card = message.card
  if (!card) return null
  if (card.type === 'approval') {
    return <ApprovalCard key={card.id} approvalId={card.id} tool={message.body_md} />
  }
  if (card.type === 'question') {
    return <QuestionCard key={card.id} questionId={card.id} text={message.body_md} />
  }
  return null
}
