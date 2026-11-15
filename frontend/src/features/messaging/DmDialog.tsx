import { useNavigate } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { AgentDmPicker } from '@/features/agents/AgentDmPicker'
import { usesAi } from '@/features/ai/display'
import { useMe } from '@/features/auth/queries'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { principalKey } from '@/features/directory/queries'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { DirectoryEntry } from '@/lib/api'
import { useOpenDm } from './queries'

/** At most nine people in a direct message: me and eight others. */
export const MAX_OTHERS = 8

/** Starts (or reopens) a direct message with up to eight other people. */
export function DmDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const withAgents = usesAi(useMe())
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('messaging.dm.openTitle')}</DialogTitle>
          <DialogDescription>
            {t('messaging.dm.openDescription', { count: MAX_OTHERS })}
          </DialogDescription>
        </DialogHeader>
        {open && <DmForm onDone={() => onOpenChange(false)} />}
        {open && withAgents && <AgentDmPicker onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function DmForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const me = useMe()
  const openDm = useOpenDm()
  const [people, setPeople] = useState<DirectoryEntry[]>([])
  const exclude = useMemo(
    () =>
      new Set([
        ...people.map(principalKey),
        ...(me ? [principalKey({ type: 'user', id: me.user.id })] : []),
      ]),
    [people, me],
  )
  const full = people.length >= MAX_OTHERS

  const submit = () => {
    if (people.length === 0) return
    openDm.mutate(
      people.map((p) => p.id),
      {
        onSuccess: (dm) => {
          onDone()
          void navigate({ to: '/c/$conversationId', params: { conversationId: dm.id } })
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {people.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={t('messaging.dm.chosen')}>
          {people.map((person) => (
            <li
              key={person.id}
              className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-sm"
            >
              {person.name}
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-background"
                aria-label={t('messaging.dm.removePerson', { name: person.name })}
                onClick={() => setPeople((all) => all.filter((p) => p.id !== person.id))}
              >
                <X className="size-3" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <Field
        label={t('messaging.dm.people')}
        hint={full ? t('messaging.dm.full', { count: MAX_OTHERS }) : undefined}
      >
        {(props) =>
          full ? (
            <span {...props} />
          ) : (
            <DirectoryCombobox
              control={props}
              type="user"
              selected={null}
              exclude={exclude}
              onSelect={(entry) => entry && setPeople((all) => [...all, entry])}
            />
          )
        }
      </Field>
      <SaveError error={openDm.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button onClick={submit} disabled={people.length === 0 || openDm.isPending}>
          {t('messaging.dm.openSubmit')}
        </Button>
      </FormActions>
    </div>
  )
}
