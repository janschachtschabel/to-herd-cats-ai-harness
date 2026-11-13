import { zodResolver } from '@hookform/resolvers/zod'
import { Eye } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import type { DirectoryEntry, InspectableDm, Inspection, Schemas } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { bodySchema } from '@/lib/schemas'
import { InspectionView } from './InspectionView'
import { useGrantInspection, useInspectableDms } from './queries'

const NOBODY = new Set<string>()
const schema = bodySchema('InspectionCreate')

/** "Look into direct messages" (spec 5.5, plan M3 decision 6): find a person's direct
 *  messages, give a reason, then read one for a limited time; read only, audited, and
 *  the participants see that it happened. Only with `dm.inspect` (the route checks). */
export function DmInspectPage() {
  const { t } = useTranslation()
  const [person, setPerson] = useState<DirectoryEntry | null>(null)
  const [chosen, setChosen] = useState<InspectableDm | null>(null)
  const [inspection, setInspection] = useState<{ grant: Inspection; dm: InspectableDm } | null>(
    null,
  )

  if (inspection) {
    return (
      <InspectionView
        inspection={inspection.grant}
        dm={inspection.dm}
        onEnd={() => setInspection(null)}
      />
    )
  }
  return (
    <div>
      <PageHeader title={t('dmInspect.title')} description={t('dmInspect.description')} />
      <Alert className="mb-6">
        <Eye aria-hidden />
        <AlertDescription>{t('dmInspect.rules')}</AlertDescription>
      </Alert>
      <div className="mb-6 max-w-md">
        <Field label={t('dmInspect.person')}>
          {(props) => (
            <DirectoryCombobox
              control={props}
              type="user"
              selected={person}
              exclude={NOBODY}
              onSelect={(entry) => {
                setPerson(entry)
                setChosen(null)
              }}
            />
          )}
        </Field>
      </div>
      {person &&
        (chosen ? (
          <ReasonForm
            dm={chosen}
            onCancel={() => setChosen(null)}
            onGranted={(grant) => setInspection({ grant, dm: chosen })}
          />
        ) : (
          <DmList userId={person.id} onChoose={setChosen} />
        ))}
    </div>
  )
}

function DmList({ userId, onChoose }: { userId: string; onChoose: (dm: InspectableDm) => void }) {
  const { t, i18n } = useTranslation()
  const dms = useInspectableDms(userId)
  if (dms.isPending) return <LoadingState rows={2} />
  if (dms.isError) return <ErrorState error={dms.error} onRetry={() => void dms.refetch()} />
  if (dms.items.length === 0) return <EmptyState text={t('dmInspect.none')} />
  return (
    <section aria-labelledby="inspect-dms">
      <h2 id="inspect-dms" className="mb-2 text-sm font-semibold">
        {t('dmInspect.dms')}
      </h2>
      <ul className="flex flex-col gap-2">
        {dms.items.map((dm) => (
          <li
            key={dm.conversation_id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{dm.participants.map((p) => p.name).join(', ')}</p>
              <p className="text-xs text-muted-foreground">
                {dm.last_message_at
                  ? t('dmInspect.lastMessage', {
                      when: formatDateTime(dm.last_message_at, i18n.language),
                    })
                  : t('dmInspect.noMessages')}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => onChoose(dm)}>
              {t('dmInspect.request')}
            </Button>
          </li>
        ))}
      </ul>
      <LoadMore hasMore={dms.hasMore} loading={dms.loadingMore} onLoad={dms.loadMore} />
    </section>
  )
}

function ReasonForm({
  dm,
  onCancel,
  onGranted,
}: {
  dm: InspectableDm
  onCancel: () => void
  onGranted: (inspection: Inspection) => void
}) {
  const { t } = useTranslation()
  const grant = useGrantInspection()
  const form = useForm<Schemas['InspectionCreate']>({
    resolver: zodResolver(schema),
    defaultValues: { conversation_id: dm.conversation_id, reason: '' },
  })
  const onSubmit = form.handleSubmit((values) =>
    grant.mutate({ ...values, reason: values.reason.trim() }, { onSuccess: onGranted }),
  )
  return (
    <form onSubmit={onSubmit} noValidate className="flex max-w-xl flex-col gap-4">
      <p className="text-sm">
        {t('dmInspect.chosen', { people: dm.participants.map((p) => p.name).join(', ') })}
      </p>
      <Field
        label={t('dmInspect.reason')}
        hint={t('dmInspect.reasonHint')}
        error={form.formState.errors.reason?.message}
      >
        {(props) => <Textarea {...props} rows={3} autoFocus {...form.register('reason')} />}
      </Field>
      <SaveError error={grant.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={grant.isPending}>
          {t('dmInspect.start')}
        </Button>
      </FormActions>
    </form>
  )
}
