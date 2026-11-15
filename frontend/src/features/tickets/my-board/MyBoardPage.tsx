import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { ApiError, type MyCard } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { ticketAbilities } from '../abilities'
import { columnCoordinates } from '../board/dnd'
import type { StatusCategory } from '../display'
import { categoryDrop, type MoveMyCard, type MyCardData, type MyCardFocus } from './dnd'
import { MyColumn } from './MyColumn'
import { useMoveToCategory, useMyBoard, useSpaceRoles } from './queries'

/** "Mein Board" (`/my-board`): the tickets assigned to me in every space I may read,
 *  in columns by status category, since each space has statuses of its own. Moving a
 *  card puts it into the first status of that category in its own space. */
export function MyBoardPage() {
  const { t } = useTranslation()
  const board = useMyBoard()
  const move = useMoveToCategory()
  const [focus, setFocus] = useState<MyCardFocus | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: columnCoordinates }),
  )
  const cards = useMemo(() => board.data?.columns.flatMap((c) => c.items) ?? [], [board.data])
  const spaceIds = useMemo(() => [...new Set(cards.map((c) => c.space_id))].sort(), [cards])
  const roles = useSpaceRoles(spaceIds)
  const movable = (spaceId: string) => ticketAbilities(roles.get(spaceId)).edit

  const onMove: MoveMyCard = (ticket, category, on) => {
    if (category === ticket.status.category) return
    if (on) setFocus({ ticketId: ticket.id, category, on })
    move.mutate(
      { ticket, category },
      {
        onError: () =>
          on && setFocus({ ticketId: ticket.id, category: ticket.status.category, on }),
      },
    )
  }
  const onDragEnd = (event: DragEndEvent) => {
    const target = categoryDrop(event)
    const keyboard = event.activatorEvent instanceof KeyboardEvent
    if (target) onMove(target.ticket, target.category, keyboard ? 'grip' : undefined)
  }

  const nameOf = (id: string | number | undefined) =>
    id ? t(`tickets.categories.${id as StatusCategory}`) : ''
  const keyOf = (data: unknown) => (data as MyCardData | undefined)?.ticket.key ?? ''
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

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t('tickets.myBoard.title')}
        description={t('tickets.myBoard.description')}
      />
      {move.error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm"
        >
          {moveError(t, move.error, move.variables)}
        </p>
      ) : null}
      {board.isPending ? (
        <LoadingState rows={3} />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => void board.refetch()} />
      ) : (
        <>
          {cards.length === 0 && <EmptyState text={t('tickets.myBoard.empty')} />}
          <DndContext
            sensors={sensors}
            onDragStart={() => move.reset()}
            onDragEnd={onDragEnd}
            accessibility={{
              announcements,
              screenReaderInstructions: { draggable: t('tickets.board.dnd.instructions') },
            }}
          >
            {/* A one-column grid keeps the columns' width out of the page's (375 px). */}
            <div className="grid grid-cols-[minmax(0,1fr)]">
              <div
                className="relative -mx-1 flex gap-3 overflow-x-auto px-1 pb-3"
                role="group"
                aria-label={t('tickets.myBoard.columns')}
              >
                {board.data.columns.map((column) => (
                  <MyColumn
                    key={column.category}
                    column={column}
                    movable={movable}
                    onMove={onMove}
                    focus={focus}
                    onFocused={() => setFocus(null)}
                  />
                ))}
              </div>
            </div>
          </DndContext>
        </>
      )}
    </div>
  )
}

/** Why a move was refused, in words: changed meanwhile, or the card's space has no
 *  status of that category (named, with the category). */
function moveError(
  t: ReturnType<typeof useTranslation>['t'],
  error: unknown,
  move: { ticket: MyCard; category: StatusCategory } | undefined,
): string {
  if (error instanceof ApiError && error.isVersionConflict) return t('tickets.board.conflict')
  if (error instanceof ApiError && error.code === 'ticket.category_empty' && move) {
    return t('tickets.myBoard.categoryEmpty', {
      space: move.ticket.space_name,
      category: t(`tickets.categories.${move.category}`),
    })
  }
  return errorMessage(t, error)
}
