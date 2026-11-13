import { useNavigate } from '@tanstack/react-router'
import { useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FormActions } from '@/features/shared/forms'
import type { WikiPage } from '@/lib/api'
import { PageParentSelect } from './PageParentSelect'
import { useMovePage } from './queries'
import { moveTargets, siblingsOf } from './tree'
import { useWiki } from './WikiContext'
import { WikiError } from './WikiError'

/** Another parent, another place among the siblings, or both (also: reordering). */
export function MovePageDialog({
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
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('wiki.move.title')}</DialogTitle>
          <DialogDescription>{t('wiki.move.description', { title: page.title })}</DialogDescription>
        </DialogHeader>
        {open && <MoveForm page={page} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function MoveForm({ page, onDone }: { page: WikiPage; onDone: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { space, nodes } = useWiki()
  const move = useMovePage(page)
  const targets = useMemo(() => moveTargets(nodes, page.id), [nodes, page.id])
  const [parentId, setParentId] = useState<string | null>(page.parent_id)
  const siblings = useMemo(() => siblingsOf(nodes, parentId, page.id), [nodes, parentId, page.id])
  const currentIndex = useMemo(() => {
    if (parentId !== page.parent_id) return siblings.length
    const index = siblings.findIndex((s) => s.sort_order > page.sort_order)
    return index === -1 ? siblings.length : index
  }, [parentId, page.parent_id, page.sort_order, siblings])
  const [position, setPosition] = useState<number | null>(null)
  const at = position ?? currentIndex

  function submit(event: FormEvent) {
    event.preventDefault()
    move.mutate(
      { parent_id: parentId, position: at },
      {
        onSuccess: (moved) => {
          onDone()
          void navigate({
            to: '/spaces/$spaceId/p/$',
            params: { spaceId: space.id, _splat: moved.path },
          })
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label={t('wiki.fields.parent')}>
        {(props) => (
          <PageParentSelect
            {...props}
            options={targets}
            value={parentId}
            onChange={(value) => {
              setParentId(value)
              setPosition(null)
            }}
          />
        )}
      </Field>
      <Field label={t('wiki.move.position')}>
        {(props) => (
          <NativeSelect {...props} value={at} onChange={(e) => setPosition(Number(e.target.value))}>
            <option value={0}>{t('wiki.move.first')}</option>
            {siblings.map((sibling, i) => (
              <option key={sibling.id} value={i + 1}>
                {t('wiki.move.after', { title: sibling.title })}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      <WikiError error={move.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={move.isPending}>
          {t('wiki.move.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
