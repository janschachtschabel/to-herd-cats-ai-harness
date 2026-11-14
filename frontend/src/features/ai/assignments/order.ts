/** The list with the item at `index` moved by `delta` places (kept within bounds). */
export function moved<T>(items: readonly T[], index: number, delta: number): T[] {
  const target = Math.max(0, Math.min(items.length - 1, index + delta))
  const next = [...items]
  const [item] = next.splice(index, 1)
  if (item === undefined) return next
  next.splice(target, 0, item)
  return next
}

export interface GroupRow {
  group_id: string
  group_name: string
  connection_id: string
  model: string
}

/** The body of `PUT /api/ai/assignments/groups`: the whole list, in its order. */
export function groupsBody(rows: readonly GroupRow[], version: number) {
  return {
    items: rows.map(({ group_id, connection_id, model }) => ({ group_id, connection_id, model })),
    version,
  }
}
