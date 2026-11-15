import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
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
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import type { User } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { CreateUserDialog } from './CreateUserDialog'
import { EditUserDialog } from './EditUserDialog'
import { useSetUserActive, useSignUserOut, useUsers } from './queries'

export function UsersPage() {
  const { t, i18n } = useTranslation()
  const users = useUsers()
  const setActive = useSetUserActive()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [toggling, setToggling] = useState<User | null>(null)
  const signOut = useSignUserOut()
  const [signingOut, setSigningOut] = useState<User | null>(null)

  const confirmToggle = () => {
    if (!toggling) return
    setActive.mutate(
      { userId: toggling.id, active: !toggling.is_active },
      { onSuccess: () => setToggling(null) },
    )
  }

  return (
    <div>
      <PageHeader
        title={t('users.title')}
        description={t('users.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('users.create.open')}
          </Button>
        }
      />
      {users.isPending ? (
        <LoadingState />
      ) : users.isError ? (
        <ErrorState error={users.error} onRetry={() => void users.refetch()} />
      ) : users.items.length === 0 ? (
        <EmptyState text={t('users.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('users.fields.name')}</TableHead>
              <TableHead>{t('users.fields.role')}</TableHead>
              <TableHead>{t('users.fields.status')}</TableHead>
              <TableHead>{t('users.fields.lastLogin')}</TableHead>
              <TableHead className="w-0">
                <span className="sr-only">{t('common.actions')}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.items.map((user) => (
              <TableRow key={user.id}>
                <TableCell>
                  <div className="font-medium">{user.name}</div>
                  <div className="text-xs text-muted-foreground">{user.email}</div>
                </TableCell>
                <TableCell>{t(`systemRoles.${user.system_role}`)}</TableCell>
                <TableCell>
                  <Badge variant={user.is_active ? 'secondary' : 'outline'}>
                    {user.is_active ? t('users.status.active') : t('users.status.inactive')}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {user.last_login_at
                    ? formatDateTime(user.last_login_at, i18n.language)
                    : t('users.neverLoggedIn')}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={t('users.edit.openNamed', { name: user.name })}
                      onClick={() => setEditing(user)}
                    >
                      {t('actions.edit')}
                    </Button>
                    {user.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={t('users.signOut.openNamed', { name: user.name })}
                        onClick={() => {
                          signOut.reset()
                          setSigningOut(user)
                        }}
                      >
                        {t('users.signOut.action')}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={t(
                        user.is_active
                          ? 'users.deactivate.openNamed'
                          : 'users.reactivate.openNamed',
                        { name: user.name },
                      )}
                      onClick={() => {
                        setActive.reset()
                        setToggling(user)
                      }}
                    >
                      {user.is_active ? t('users.deactivate.action') : t('users.reactivate.action')}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore hasMore={users.hasMore} loading={users.loadingMore} onLoad={users.loadMore} />
      <CreateUserDialog open={creating} onOpenChange={setCreating} />
      <EditUserDialog user={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={toggling !== null}
        title={toggling?.is_active ? t('users.deactivate.title') : t('users.reactivate.title')}
        text={t(toggling?.is_active ? 'users.deactivate.text' : 'users.reactivate.text', {
          name: toggling?.name ?? '',
        })}
        confirmLabel={
          toggling?.is_active ? t('users.deactivate.action') : t('users.reactivate.action')
        }
        destructive={toggling?.is_active}
        pending={setActive.isPending}
        error={setActive.error}
        onConfirm={confirmToggle}
        onOpenChange={(open) => !open && setToggling(null)}
      />
      <ConfirmDialog
        open={signingOut !== null}
        title={t('users.signOut.title')}
        text={t('users.signOut.text', { name: signingOut?.name ?? '' })}
        confirmLabel={t('users.signOut.action')}
        destructive
        pending={signOut.isPending}
        error={signOut.error}
        onConfirm={() =>
          signingOut && signOut.mutate(signingOut.id, { onSuccess: () => setSigningOut(null) })
        }
        onOpenChange={(open) => !open && setSigningOut(null)}
      />
    </div>
  )
}
