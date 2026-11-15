import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { GroupDialog } from './GroupDialog'
import { GroupMembers } from './GroupMembers'
import { useDeleteGroup, useGroup } from './queries'

export function GroupPage({ groupId }: { groupId: string }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const group = useGroup(groupId)
  const remove = useDeleteGroup()
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  if (group.isPending) return <LoadingState />
  if (group.isError) return <ErrorState error={group.error} onRetry={() => void group.refetch()} />

  return (
    <div>
      <Link
        to="/admin/groups"
        className="mb-4 inline-flex items-center gap-1 rounded-sm text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden />
        {t('groups.back')}
      </Link>
      <PageHeader
        title={group.data.name}
        description={group.data.description ?? undefined}
        actions={
          <>
            <Button variant="outline" onClick={() => setEditing(true)}>
              {t('actions.edit')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                remove.reset()
                setDeleting(true)
              }}
            >
              {t('actions.delete')}
            </Button>
          </>
        }
      />
      <section aria-labelledby="group-members-heading">
        <h2 id="group-members-heading" className="mb-3 text-base font-semibold">
          {t('groups.members.title')}
        </h2>
        <GroupMembers groupId={groupId} />
      </section>
      <GroupDialog open={editing} group={group.data} onOpenChange={setEditing} />
      <ConfirmDialog
        open={deleting}
        title={t('groups.delete.title')}
        text={t('groups.delete.text', { name: group.data.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(groupId, { onSuccess: () => void navigate({ to: '/admin/groups' }) })
        }
        onOpenChange={setDeleting}
      />
    </div>
  )
}
