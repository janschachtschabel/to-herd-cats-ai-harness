import { X } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { useWiki } from '../WikiContext'
import { useSpaceTags } from './queries'

/** Narrows the tree to the pages with one tag; shown once the space has tags to use. */
export function TreeTagFilter() {
  const { t } = useTranslation()
  const id = useId()
  const { space, tagFilter, filterByTag } = useWiki()
  const tags = useSpaceTags(space.id)
  const list = tags.data ?? []
  if (list.length === 0 && tagFilter === null) return null
  return (
    <div className="mb-3 flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {t('wiki.tagFilter.label')}
      </Label>
      <div className="flex items-center gap-1">
        <NativeSelect
          id={id}
          value={tagFilter ?? ''}
          onChange={(event) => filterByTag(event.target.value || null)}
        >
          <option value="">{t('wiki.tagFilter.all')}</option>
          {list.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </NativeSelect>
        {tagFilter !== null && (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={t('wiki.tagFilter.clear')}
            title={t('wiki.tagFilter.clear')}
            onClick={() => filterByTag(null)}
          >
            <X aria-hidden />
          </Button>
        )}
      </div>
    </div>
  )
}
