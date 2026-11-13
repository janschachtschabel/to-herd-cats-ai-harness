import { Pencil, Tag as TagIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { WikiPage } from '@/lib/api'
import { useWiki } from '../WikiContext'
import { useSpaceTags } from './queries'
import { TagsDialog } from './TagsDialog'

/** The page's tags by name, each with its colour; a tag narrows the tree to the pages
 *  carrying it. Whoever may edit the page changes its tags here. Unknown ids are left
 *  out (a tag deleted in the meantime). */
export function PageTags({ page }: { page: WikiPage }) {
  const { t } = useTranslation()
  const { space, abilities, filterByTag } = useWiki()
  const tags = useSpaceTags(space.id)
  const [editing, setEditing] = useState(false)
  const byId = new Map((tags.data ?? []).map((tag) => [tag.id, tag]))
  const shown = page.tags.flatMap((id) => byId.get(id) ?? [])
  if (shown.length === 0 && !abilities.edit) return null
  return (
    <>
      <ul className="flex flex-wrap items-center gap-1.5" aria-label={t('wiki.tags.list')}>
        {shown.map((tag) => (
          <li key={tag.id}>
            <button
              type="button"
              onClick={() => filterByTag(tag.id)}
              aria-label={t('wiki.tagFilter.showTagged', { name: tag.name })}
              title={t('wiki.tagFilter.showTagged', { name: tag.name })}
              className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span
                aria-hidden
                className="size-2 rounded-full"
                style={{ backgroundColor: tag.color }}
              />
              {tag.name}
            </button>
          </li>
        ))}
        {abilities.edit && (
          <li>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-xs"
              // Icon only next to tags; spelled out when the page has none yet.
              aria-label={shown.length > 0 ? t('wiki.tags.edit') : undefined}
              title={t('wiki.tags.edit')}
              onClick={() => setEditing(true)}
            >
              {shown.length > 0 ? (
                <Pencil aria-hidden />
              ) : (
                <>
                  <TagIcon aria-hidden />
                  {t('wiki.tags.edit')}
                </>
              )}
            </Button>
          </li>
        )}
      </ul>
      {abilities.edit && <TagsDialog page={page} open={editing} onOpenChange={setEditing} />}
    </>
  )
}
