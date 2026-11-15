import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Space } from '@/lib/api'
import {
  checkValues,
  createBody,
  newValues,
  scheduleOf,
  updateBody,
  valuesOf,
  type AutomationValues,
  type FieldErrors,
  type Kind,
  type PlaceType,
} from './form'
import { EventFields, HeartbeatFields } from './HeartbeatEventFields'
import { AgentField, PlaceFields } from './PlaceFields'
import {
  useCreateAutomation,
  useReloadAutomation,
  useUpdateAutomation,
  type Automation,
} from './queries'
import { KindField, OnceFields, RecurringFields } from './ScheduleFields'
import { TermPreview } from './TermPreview'
import { viewerZone } from './zoned'

/** Make an automation (`automation` absent; in `space` its places are the space's and,
 *  for who manages it, event rules may be made), or change one (its kind stays). */
export function AutomationFormDialog({
  open,
  onOpenChange,
  automation,
  space = null,
  eventRules = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  automation?: Automation
  space?: Space | null
  eventRules?: boolean
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {automation ? t('automations.form.editTitle') : t('automations.form.createTitle')}
          </DialogTitle>
          <DialogDescription>{t('automations.form.description')}</DialogDescription>
        </DialogHeader>
        {open && (
          <AutomationForm
            automation={automation}
            space={space}
            eventRules={eventRules}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

const KINDS: readonly Kind[] = ['once', 'recurring', 'heartbeat']
const PLACES: readonly PlaceType[] = ['dm', 'channel', 'ticket']
const SPACE_PLACES: readonly PlaceType[] = ['channel', 'ticket']

function AutomationForm({
  automation,
  space,
  eventRules,
  onDone,
}: {
  automation?: Automation
  space: Space | null
  eventRules: boolean
  onDone: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const create = useCreateAutomation()
  const update = useUpdateAutomation(automation?.id ?? '')
  const reload = useReloadAutomation(automation?.id ?? '')
  const save = automation ? update : create
  const [values, setValues] = useState<AutomationValues>(() =>
    automation
      ? valuesOf(automation, viewerZone())
      : newValues({ zone: viewerZone(), agent: null, placeType: space ? 'channel' : 'dm' }),
  )
  const [errors, setErrors] = useState<FieldErrors>({})
  const [version, setVersion] = useState(automation?.version ?? 0)
  const change = (patch: Partial<AutomationValues>) => setValues((v) => ({ ...v, ...patch }))
  const kinds: readonly Kind[] = eventRules ? [...KINDS, 'event'] : KINDS
  const places = space ? SPACE_PLACES : PLACES
  const heartbeat = values.kind === 'heartbeat'

  /** After a stale version: the current one, what was typed kept. */
  const reloaded = async () => {
    const fresh = await reload()
    setVersion(fresh.version)
    update.reset()
  }

  const submit = () => {
    const found = checkValues(values, automation ? 'edit' : 'create')
    setErrors(found)
    if (Object.keys(found).length > 0) return
    if (automation) {
      update.mutate(updateBody(values, { ...automation, version }), { onSuccess: onDone })
      return
    }
    create.mutate(createBody(values), {
      onSuccess: (made) => {
        onDone()
        if (made)
          void navigate({ to: '/automations/$automationId', params: { automationId: made.id } })
      },
    })
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {automation ? (
        <p className="text-sm text-muted-foreground">{t('automations.form.kindFixed')}</p>
      ) : (
        <>
          <KindField
            kinds={kinds}
            value={values.kind}
            onChange={(kind) =>
              change(
                kind === 'event' && values.placeType === 'dm'
                  ? { kind, placeType: 'channel' }
                  : { kind },
              )
            }
          />
          <AgentField values={values} errors={errors} onChange={change} />
          <PlaceFields
            values={values}
            errors={errors}
            onChange={change}
            types={values.kind === 'event' ? SPACE_PLACES : places}
            spaceId={space?.id ?? null}
          />
        </>
      )}
      <Field
        label={t(heartbeat ? 'automations.form.checklist' : 'automations.form.instruction')}
        hint={t(heartbeat ? 'automations.form.checklistHint' : 'automations.form.instructionHint')}
        error={errors.instruction}
      >
        {(props) => (
          <Textarea
            {...props}
            rows={4}
            value={values.instruction}
            onChange={(e) => change({ instruction: e.target.value })}
          />
        )}
      </Field>
      {values.kind === 'once' && <OnceFields values={values} errors={errors} onChange={change} />}
      {values.kind === 'recurring' && (
        <RecurringFields values={values} errors={errors} onChange={change} />
      )}
      {values.kind === 'heartbeat' && (
        <HeartbeatFields values={values} errors={errors} onChange={change} />
      )}
      {values.kind === 'event' && space && (
        <EventFields values={values} errors={errors} onChange={change} spaceId={space.id} />
      )}
      {values.kind !== 'event' && <TermPreview schedule={scheduleOf(values)} />}
      <SaveError error={save.error} onReload={automation ? () => void reloaded() : undefined} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {automation ? t('actions.save') : t('automations.form.create')}
        </Button>
      </FormActions>
    </form>
  )
}
