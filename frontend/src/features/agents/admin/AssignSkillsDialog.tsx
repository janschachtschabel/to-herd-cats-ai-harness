import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { FormActions, SaveError } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useSkills } from '@/features/skills/queries'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useSetAgentSkills } from '../adminQueries'
import type { AgentSkill } from '../levels'

/** Choose the agent's skills from the active ones the API offers this person (its
 *  search narrows by name). Skills already assigned stay unless unticked. */
export function AssignSkillsDialog({
  open,
  agentId,
  assigned,
  version,
  onOpenChange,
}: {
  open: boolean
  agentId: string
  assigned: readonly AgentSkill[]
  version: number
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('agents.skills.assignTitle')}</DialogTitle>
          <DialogDescription>{t('agents.skills.assignHint')}</DialogDescription>
        </DialogHeader>
        {open && (
          <AssignForm
            agentId={agentId}
            assigned={assigned}
            version={version}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function AssignForm({
  agentId,
  assigned,
  version,
  onDone,
}: {
  agentId: string
  assigned: readonly AgentSkill[]
  version: number
  onDone: () => void
}) {
  const { t } = useTranslation()
  const [chosen, setChosen] = useState<string[]>(assigned.map((s) => s.id))
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search.trim(), 300)
  const offered = useSkills({ state: 'active', q })
  const save = useSetAgentSkills(agentId)
  const shown = [
    ...assigned.filter((s) => !offered.items.some((o) => o.id === s.id) && !q),
    ...offered.items,
  ]

  const toggle = (id: string, on: boolean) =>
    setChosen((ids) => (on ? [...ids, id] : ids.filter((other) => other !== id)))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ skill_ids: chosen, version }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Input
        type="search"
        aria-label={t('agents.skills.search')}
        placeholder={t('agents.skills.search')}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {offered.isPending ? (
        <LoadingState rows={3} />
      ) : offered.isError ? (
        <ErrorState error={offered.error} onRetry={() => void offered.refetch()} />
      ) : shown.length === 0 ? (
        <EmptyState text={t('agents.skills.noneOffered')} />
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {shown.map((skill) => (
            <li key={skill.id}>
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1 accent-primary"
                  checked={chosen.includes(skill.id)}
                  onChange={(e) => toggle(skill.id, e.target.checked)}
                />
                <span>
                  <span className="font-medium">{skill.name}</span>
                  <span className="block text-xs text-muted-foreground">{skill.description}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={offered.hasMore} loading={offered.loadingMore} onLoad={offered.loadMore} />
      <SaveError error={save.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
