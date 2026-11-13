import { useSpaceTags } from './queries'

/** The page's tags by name, each with its colour; unknown ids are left out. */
export function TagChips({ spaceId, tagIds }: { spaceId: string; tagIds: string[] }) {
  const tags = useSpaceTags(spaceId)
  if (tagIds.length === 0 || !tags.data) return null
  const byId = new Map(tags.data.map((tag) => [tag.id, tag]))
  return (
    <ul className="flex flex-wrap gap-1.5">
      {tagIds.flatMap((id) => {
        const tag = byId.get(id)
        if (!tag) return []
        return [
          <li
            key={id}
            className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-foreground"
          >
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ backgroundColor: tag.color }}
            />
            {tag.name}
          </li>,
        ]
      })}
    </ul>
  )
}
