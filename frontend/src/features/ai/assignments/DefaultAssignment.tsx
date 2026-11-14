import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import type { Connection } from '../display'
import { useSetDefault } from '../assignmentQueries'
import { TargetPicker, type Target } from './TargetPicker'

function targetOf(target: Schemas['TargetOut'] | null): Target | null {
  return target ? { connection_id: target.connection_id, model: target.model } : null
}

/** The organisation's standard: who has no person or group assignment uses it; empty
 *  means nobody has AI until an administrator assigns it. */
export function DefaultAssignment({
  overview,
  connections,
  onReload,
}: {
  overview: Schemas['AssignmentsOut']
  connections: readonly Connection[]
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetDefault()
  const [target, setTarget] = useState<Target | null>(targetOf(overview.default))
  const [saved, setSaved] = useState(false)

  return (
    <section aria-labelledby="ai-default-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="ai-default-heading" className="font-semibold">
          {t('ai.assignments.defaultTitle')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('ai.assignments.defaultHint')}</p>
      </div>
      <TargetPicker
        connections={connections}
        value={target}
        onChange={(next) => {
          setTarget(next)
          setSaved(false)
        }}
        noneLabel={t('ai.assignments.noDefault')}
        label={t('ai.assignments.defaultTitle')}
      />
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          disabled={save.isPending || (target !== null && target.model === '')}
          onClick={() =>
            save.mutate({ target, version: overview.version }, { onSuccess: () => setSaved(true) })
          }
        >
          {t('actions.save')}
        </Button>
        {saved && (
          <span role="status" className="text-sm text-muted-foreground">
            {t('ai.assignments.saved')}
          </span>
        )}
      </div>
      <SaveError
        error={save.error}
        onReload={() => {
          save.reset()
          onReload()
        }}
      />
    </section>
  )
}
