import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { FormActions } from '@/features/shared/forms'
import { ErrorState, LoadingState } from '@/features/shared/states'
import type { WikiPage } from '@/lib/api'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { useCreateSpaceTag, useSetPageTags, useSpaceTags } from './queries'

export function TagsDialog({
  page,
  open,
  onOpenChange,
}: {
  page: WikiPage
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('wiki.tags.title')}</DialogTitle>
          <DialogDescription>{t('wiki.tags.description')}</DialogDescription>
        </DialogHeader>
        {open && <TagsForm page={page} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function TagsForm({ page, onDone }: { page: WikiPage; onDone: () => void }) {
  const { t } = useTranslation()
  const { space, abilities } = useWiki()
  const tags = useSpaceTags(space.id)
  const save = useSetPageTags(page)
  const [chosen, setChosen] = useState<Set<string>>(() => new Set(page.tags))

  function toggle(id: string) {
    setChosen((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate([...chosen], { onSuccess: onDone })
  }

  if (tags.isPending) return <LoadingState rows={2} />
  if (tags.isError) return <ErrorState error={tags.error} onRetry={() => void tags.refetch()} />
  return (
    <div className="flex flex-col gap-4">
      <form id="page-tags" onSubmit={submit}>
        <fieldset className="flex flex-col gap-1">
          <legend className="sr-only">{t('wiki.tags.title')}</legend>
          {tags.data.length === 0 && (
            <p className="text-sm text-muted-foreground">{t('wiki.tags.none')}</p>
          )}
          {tags.data.map((tag) => (
            <label
              key={tag.id}
              className="flex items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-accent"
            >
              <input
                type="checkbox"
                className="accent-primary"
                checked={chosen.has(tag.id)}
                onChange={() => toggle(tag.id)}
              />
              <span
                aria-hidden
                className="size-2.5 rounded-full"
                style={{ backgroundColor: tag.color }}
              />
              {tag.name}
            </label>
          ))}
        </fieldset>
      </form>
      {abilities.moderate && <NewTag spaceId={space.id} onCreated={(id) => toggle(id)} />}
      <WikiError error={save.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" form="page-tags" disabled={save.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </div>
  )
}

/** A new tag of this space (moderators), chosen for the page at once. */
function NewTag({ spaceId, onCreated }: { spaceId: string; onCreated: (id: string) => void }) {
  const { t } = useTranslation()
  const create = useCreateSpaceTag(spaceId)
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate(name.trim(), {
      onSuccess: (tag) => {
        setName('')
        onCreated(tag.id)
      },
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2" aria-label={t('wiki.tags.new')}>
      <div className="flex gap-2">
        <Input
          aria-label={t('wiki.tags.newName')}
          placeholder={t('wiki.tags.newName')}
          maxLength={50}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit" variant="outline" disabled={create.isPending || !name.trim()}>
          <Plus aria-hidden />
          {t('wiki.tags.add')}
        </Button>
      </div>
      <WikiError error={create.error} />
    </form>
  )
}
