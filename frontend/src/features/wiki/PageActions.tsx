import { Link, useNavigate } from '@tanstack/react-router'
import {
  Download,
  FilePlus,
  FolderInput,
  History,
  MoreHorizontal,
  Pencil,
  Send,
  Tags,
  TextCursorInput,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import type { WikiPage } from '@/lib/api'
import { canPublish } from './abilities'
import { MovePageDialog } from './MovePageDialog'
import { usePublishPage } from './queries'
import { RenamePageDialog } from './RenamePageDialog'
import { TagsDialog } from './tags/TagsDialog'
import { pageExportUrl } from './transfer/queries'
import { useTrashPage } from './trash/queries'
import { useWiki } from './WikiContext'
import { WikiError } from './WikiError'

type Open = 'rename' | 'move' | 'tags' | 'trash' | null

/** What one may do with the page; each action shown only with the right for it. */
export function PageActions({ page }: { page: WikiPage }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { space, me, abilities, createPage } = useWiki()
  const [open, setOpen] = useState<Open>(null)
  const publish = usePublishPage(page)
  const trash = useTrashPage(page)
  const close = (next: boolean) => !next && setOpen(null)
  const params = { spaceId: space.id, _splat: page.path }

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap justify-end gap-2">
        {abilities.edit && (
          <>
            <Button variant="outline" asChild>
              <Link to="/spaces/$spaceId/p/$" params={params} search={{ view: 'edit' }}>
                <Pencil aria-hidden />
                {t('wiki.actions.edit')}
              </Link>
            </Button>
          </>
        )}
        {canPublish(abilities, page, me) && (
          <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
            <Send aria-hidden />
            {t('wiki.actions.publish')}
          </Button>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t('wiki.actions.more')}>
              <MoreHorizontal aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to="/spaces/$spaceId/p/$" params={params} search={{ view: 'versions' }}>
                <History aria-hidden />
                {t('wiki.actions.versions')}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href={pageExportUrl(page.id)} download>
                <Download aria-hidden />
                {t('wiki.actions.exportPage')}
              </a>
            </DropdownMenuItem>
            {abilities.create && (
              <DropdownMenuItem onSelect={() => createPage({ parentId: page.id })}>
                <FilePlus aria-hidden />
                {t('wiki.actions.createChild')}
              </DropdownMenuItem>
            )}
            {abilities.edit && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setOpen('rename')}>
                  <TextCursorInput aria-hidden />
                  {t('wiki.actions.rename')}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setOpen('move')}>
                  <FolderInput aria-hidden />
                  {t('wiki.actions.move')}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setOpen('tags')}>
                  <Tags aria-hidden />
                  {t('wiki.actions.tags')}
                </DropdownMenuItem>
              </>
            )}
            {abilities.trash && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setOpen('trash')}>
                  <Trash2 aria-hidden />
                  {t('wiki.actions.trash')}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <WikiError error={publish.error} />
      {abilities.edit && (
        <>
          <RenamePageDialog page={page} open={open === 'rename'} onOpenChange={close} />
          <MovePageDialog page={page} open={open === 'move'} onOpenChange={close} />
          <TagsDialog page={page} open={open === 'tags'} onOpenChange={close} />
        </>
      )}
      {abilities.trash && (
        <ConfirmDialog
          open={open === 'trash'}
          title={t('wiki.trash.confirmTitle')}
          text={t('wiki.trash.confirmText', { title: page.title })}
          confirmLabel={t('wiki.actions.trash')}
          destructive
          pending={trash.isPending}
          error={trash.error}
          errorView={<WikiError error={trash.error} />}
          onOpenChange={close}
          onConfirm={() =>
            trash.mutate(undefined, {
              onSuccess: () => {
                setOpen(null)
                void navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } })
              },
            })
          }
        />
      )}
    </div>
  )
}
