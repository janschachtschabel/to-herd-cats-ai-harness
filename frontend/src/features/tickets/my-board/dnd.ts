import type { DragEndEvent } from '@dnd-kit/core'
import type { MyCard } from '@/lib/api'
import type { StatusCategory } from '../display'

/** What a card of my board carries while it is dragged. */
export interface MyCardData {
  ticket: MyCard
}

/** Where the focus goes once a card moved by keyboard or menu shows in its column. */
export interface MyCardFocus {
  ticketId: string
  category: StatusCategory
  on: 'grip' | 'menu'
}

export type MoveMyCard = (ticket: MyCard, category: StatusCategory, on?: MyCardFocus['on']) => void

/** A finished drag as a move: the card and the column (category) it was dropped on;
 *  null where it went nowhere or stayed in its column. */
export function categoryDrop(
  event: Pick<DragEndEvent, 'active' | 'over'>,
): { ticket: MyCard; category: StatusCategory } | null {
  const ticket = (event.active.data.current as MyCardData | undefined)?.ticket
  const category = event.over ? (String(event.over.id) as StatusCategory) : null
  if (!ticket || !category || category === ticket.status.category) return null
  return { ticket, category }
}
