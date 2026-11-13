import type { DragEndEvent, KeyboardCoordinateGetter } from '@dnd-kit/core'
import type { TicketSummary } from '@/lib/api'

/** What a card carries while it is dragged. */
export interface CardData {
  ticket: TicketSummary
}

/** A finished drag as a move: the card and the column (status) it was dropped on;
 *  null where it went nowhere or stayed in its column. */
export function dropTarget(
  event: Pick<DragEndEvent, 'active' | 'over'>,
): { ticket: TicketSummary; statusId: string } | null {
  const ticket = (event.active.data.current as CardData | undefined)?.ticket
  const statusId = event.over ? String(event.over.id) : null
  if (!ticket || !statusId || statusId === ticket.status.id) return null
  return { ticket, statusId }
}

/** The keyboard way across the board: with a card picked up (Space or Enter), Left and
 *  Right move it to the neighbouring column; Up and Down do nothing (a column has a
 *  fixed order, plan M4 decision 8). */
export const columnCoordinates: KeyboardCoordinateGetter = (
  event,
  { currentCoordinates, context },
) => {
  const step = event.code === 'ArrowRight' ? 1 : event.code === 'ArrowLeft' ? -1 : 0
  if (step === 0) return undefined
  event.preventDefault()
  const { droppableRects, over, collisionRect } = context
  if (!collisionRect) return undefined
  const columns = [...droppableRects.entries()].sort(([, a], [, b]) => a.left - b.left)
  const here = columns.findIndex(([id]) => id === over?.id)
  const next = columns[here + step]
  if (here < 0 || !next) return undefined
  const [, rect] = next
  return {
    x: currentCoordinates.x + (rect.left + 8 - collisionRect.left),
    y: currentCoordinates.y + (rect.top + 40 - collisionRect.top),
  }
}
