import { Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import type { Tag } from '@/lib/api'
import { type TagScope, useDeleteTag } from './queries'
import { TagDialog } from './TagDialog'

/** Tags of one scope with their colour; each can be changed or deleted (the caller
 *  shows the table only to people who may). */
export function TagTable({ scope, tags }: { scope: TagScope; tags: Tag[] }) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState<Tag | null>(null)
  const [deleting, setDeleting] = useState<Tag | null>(null)
  const remove = useDeleteTag()

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">{t('tags.fields.color')}</TableHead>
            <TableHead>{t('tags.fields.name')}</TableHead>
            <TableHead className="w-24 text-right">{t('common.actions')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tags.map((tag) => (
            <TableRow key={tag.id}>
              <TableCell>
                <span
                  role="img"
                  aria-label={tag.color}
                  className="block size-4 rounded-full border"
                  style={{ backgroundColor: tag.color }}
                />
              </TableCell>
              <TableCell className="font-medium">{tag.name}</TableCell>
              <TableCell className="text-right">
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={t('tags.edit.open', { name: tag.name })}
                  title={t('tags.edit.open', { name: tag.name })}
                  onClick={() => setEditing(tag)}
                >
                  <Pencil aria-hidden />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={t('tags.delete.open', { name: tag.name })}
                  title={t('tags.delete.open', { name: tag.name })}
                  onClick={() => {
                    remove.reset()
                    setDeleting(tag)
                  }}
                >
                  <Trash2 aria-hidden />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <TagDialog
        open={editing !== null}
        scope={scope}
        tag={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
      />
      <ConfirmDialog
        open={deleting !== null}
        title={t('tags.delete.title')}
        text={t('tags.delete.text', { name: deleting?.name ?? '' })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={(open) => !open && setDeleting(null)}
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })
        }}
      />
    </>
  )
}
