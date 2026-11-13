import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { ticketAbilities } from '../abilities'
import { CreateTicketDialog } from '../CreateTicketDialog'
import { BoardColumn } from './BoardColumn'
import { BoardFilterBar } from './BoardFilterBar'
import { type CardData, type CardFocus, columnCoordinates, dropTarget, type MoveCard } from './dnd'
import { type BoardFilters, useBoard, useMoveTicket } from './queries'

/** A space's board (`/spaces/<id>/board`): its statuses as columns in their order.
 *  Moving a card changes its status at once; a refusal puts it back and says why. */
export function BoardView() {
  const { t } = useTranslation()
  const { space } = useWiki()
  const abilities = ticketAbilities(space.my_role)
  const [filters, setFilters] = useState<BoardFilters>({})
  const board = useBoard(space.id, filters)
  const move = useMoveTicket(space.id, filters)
  const [creating, setCreating] = useState(false)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: columnCoordinates }),
  )

  const [focus, setFocus] = useState<CardFocus | null>(null)

  // One way for dragging and the menu. Moved by keyboard or menu, the card takes the
  // focus along to its new column (and back, if the move is refused).
  const onMove: MoveCard = (ticket, statusId, on) => {
    if (statusId === ticket.status.id) return
    if (on) setFocus({ ticketId: ticket.id, statusId, on })
    move.mutate(
      { ticket, statusId },
      { onError: () => on && setFocus({ ticketId: ticket.id, statusId: ticket.status.id, on }) },
    )
  }
  const onDragEnd = (event: DragEndEvent) => {
    const target = dropTarget(event)
    const keyboard = event.activatorEvent instanceof KeyboardEvent
    if (target) onMove(target.ticket, target.statusId, keyboard ? 'grip' : undefined)
  }

  const nameOf = (id: string | number | undefined) =>
    board.data?.columns.find((c) => c.status.id === id)?.status.name ?? ''
  const keyOf = (data: unknown) => (data as CardData | undefined)?.ticket.key ?? ''
  const announcements: Announcements = {
    onDragStart: ({ active }) => t('tickets.board.dnd.start', { key: keyOf(active.data.current) }),
    onDragOver: ({ active, over }) =>
      over
        ? t('tickets.board.dnd.over', { key: keyOf(active.data.current), status: nameOf(over.id) })
        : t('tickets.board.dnd.outside', { key: keyOf(active.data.current) }),
    onDragEnd: ({ active, over }) =>
      over
        ? t('tickets.board.dnd.end', { key: keyOf(active.data.current), status: nameOf(over.id) })
        : t('tickets.board.dnd.cancel', { key: keyOf(active.data.current) }),
    onDragCancel: ({ active }) =>
      t('tickets.board.dnd.cancel', { key: keyOf(active.data.current) }),
  }

  const conflict = move.error instanceof ApiError && move.error.isVersionConflict
  return (
    <section aria-labelledby="board-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="board-title" className="text-base font-semibold">
          {t('tickets.board.title')}
        </h2>
        {abilities.create && (
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('tickets.create.open')}
          </Button>
        )}
      </div>
      <BoardFilterBar spaceId={space.id} filters={filters} onChange={setFilters} />
      {move.error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm"
        >
          {conflict ? t('tickets.board.conflict') : errorMessage(t, move.error)}
        </p>
      ) : null}
      {board.isPending ? (
        <LoadingState rows={3} />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => void board.refetch()} />
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={() => move.reset()}
          onDragEnd={onDragEnd}
          accessibility={{
            announcements,
            screenReaderInstructions: { draggable: t('tickets.board.dnd.instructions') },
          }}
        >
          <div
            className="relative -mx-1 flex gap-3 overflow-x-auto px-1 pb-3"
            role="group"
            aria-label={t('tickets.board.columns')}
          >
            {board.data.columns.map((column) => (
              <BoardColumn
                key={column.status.id}
                spaceId={space.id}
                column={column}
                statuses={board.data.columns.map((c) => c.status)}
                filters={filters}
                movable={abilities.edit}
                onMove={onMove}
                focus={focus}
                onFocused={() => setFocus(null)}
              />
            ))}
          </div>
        </DndContext>
      )}
      {abilities.create && (
        <CreateTicketDialog
          open={creating}
          onOpenChange={setCreating}
          spaces={[space]}
          onCreated={() => undefined}
        />
      )}
    </section>
  )
}
