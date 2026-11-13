import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { CATEGORIES, type StatusCategory } from '../display'
import { useStatuses } from '../queries'
import { useCreateStatus } from './queries'
import { StatusRow } from './StatusRow'

export const MAX_STATUSES = 20

/** The space's ticket workflow (space settings, `space.manage` only): its statuses in
 *  order, each with a name and a category (the logic reads only the category); add,
 *  rename, re-categorise, reorder, delete with a status for its tickets. */
export function StatusSettings({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const statuses = useStatuses(spaceId)
  return (
    <section aria-labelledby="statuses-heading" className="mt-8">
      <h3 id="statuses-heading" className="mb-1 text-base font-semibold">
        {t('tickets.statuses.title')}
      </h3>
      <p className="mb-3 text-sm text-muted-foreground">{t('tickets.statuses.description')}</p>
      {statuses.isPending ? (
        <LoadingState rows={3} />
      ) : statuses.isError ? (
        <ErrorState error={statuses.error} onRetry={() => void statuses.refetch()} />
      ) : (
        <>
          <ol className="flex flex-col divide-y rounded-lg border">
            {statuses.data.map((status, index) => (
              <StatusRow
                key={`${status.id}-${status.name}`}
                status={status}
                others={statuses.data.filter((s) => s.id !== status.id)}
                first={index === 0}
                last={index === statuses.data.length - 1}
              />
            ))}
          </ol>
          <NewStatus spaceId={spaceId} full={statuses.data.length >= MAX_STATUSES} />
        </>
      )}
    </section>
  )
}

function NewStatus({ spaceId, full }: { spaceId: string; full: boolean }) {
  const { t } = useTranslation()
  const create = useCreateStatus(spaceId)
  const [name, setName] = useState('')
  const [category, setCategory] = useState<StatusCategory>('active')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate({ name: name.trim(), category }, { onSuccess: () => setName('') })
  }
  const tooMany =
    full || (create.error instanceof ApiError && create.error.code === 'ticket_status.too_many')
  return (
    <form
      onSubmit={submit}
      className="mt-3 flex flex-col gap-2"
      aria-label={t('tickets.statuses.new')}
    >
      <div className="flex flex-wrap gap-2">
        <Input
          aria-label={t('tickets.statuses.name')}
          placeholder={t('tickets.statuses.newName')}
          maxLength={40}
          className="min-w-40 flex-1"
          value={name}
          disabled={full}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="w-40">
          <NativeSelect
            aria-label={t('tickets.statuses.category')}
            value={category}
            disabled={full}
            onChange={(e) => setCategory(e.target.value as StatusCategory)}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`tickets.categories.${c}`)}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button type="submit" variant="outline" disabled={full || create.isPending || !name.trim()}>
          <Plus aria-hidden />
          {t('tickets.statuses.add')}
        </Button>
      </div>
      {tooMany ? (
        <p className="text-xs text-muted-foreground">
          {t('tickets.statuses.tooMany', { count: MAX_STATUSES })}
        </p>
      ) : create.error ? (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, create.error)}
        </p>
      ) : null}
    </form>
  )
}
