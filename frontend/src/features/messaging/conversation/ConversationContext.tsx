import { createContext, useContext } from 'react'
import type { Conversation } from '@/lib/api'
import type { ConversationAbilities } from '../abilities'

/** What every message of an open conversation shares. */
export interface ConversationView {
  conversation: Conversation
  abilities: ConversationAbilities
  meId: string | undefined
  /** Opens a message's thread; absent where threads are not offered (inside one). */
  openThread?: (messageId: string) => void
  /** The message to scroll to and mark (from a search hit or the activity). */
  highlight?: string
}

export const ConversationContext = createContext<ConversationView | null>(null)

export function useConversationView(): ConversationView {
  const view = useContext(ConversationContext)
  if (!view) throw new Error('useConversationView outside of a conversation')
  return view
}
