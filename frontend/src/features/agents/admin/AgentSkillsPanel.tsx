import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import { useAgentSkills, useSetAgentSkills } from '../adminQueries'
import { unavailableReason } from '../levels'
import { AssignSkillsDialog } from './AssignSkillsDialog'

/** The agent's skills: in a run it sees each one's name and description and loads
 *  the text when it needs it. One it cannot use now says why. */
export function AgentSkillsPanel({ agentId, onReload }: { agentId: string; onReload: () => void }) {
  const { t } = useTranslation()
  const skills = useAgentSkills(agentId)
  const save = useSetAgentSkills(agentId)
  const [assigning, setAssigning] = useState(false)

  return (
    <section aria-labelledby="agent-skills" className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="agent-skills" className="text-base font-semibold">
          {t('agents.skills.title')}
        </h2>
        <Button size="sm" variant="outline" onClick={() => setAssigning(true)}>
          {t('agents.skills.assign')}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">{t('agents.skills.hint')}</p>
      {skills.isPending ? (
        <LoadingState rows={2} />
      ) : skills.isError ? (
        <ErrorState error={skills.error} onRetry={() => void skills.refetch()} />
      ) : skills.data.skills.length === 0 ? (
        <EmptyState text={t('agents.skills.empty')} />
      ) : (
        <ul aria-label={t('agents.skills.listLabel')} className="divide-y text-sm">
          {skills.data.skills.map((skill) => {
            const reason = unavailableReason(skill)
            const rest = skills.data.skills.filter((s) => s.id !== skill.id).map((s) => s.id)
            return (
              <li key={skill.id} className="flex items-start justify-between gap-2 py-2">
                <div className="min-w-0">
                  <span className="font-medium">{skill.name}</span>
                  <p className="text-muted-foreground">{skill.description}</p>
                  {reason && (
                    <Badge variant="destructive" className="mt-1 h-auto whitespace-normal">
                      {t(`agents.skills.unavailable.${reason}`)}
                    </Badge>
                  )}
                </div>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t('agents.skills.removeNamed', { name: skill.name })}
                  disabled={save.isPending}
                  onClick={() => save.mutate({ skill_ids: rest, version: skills.data.version })}
                >
                  <X aria-hidden />
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      <SaveError error={save.error} onReload={onReload} />
      {skills.data && (
        <AssignSkillsDialog
          open={assigning}
          agentId={agentId}
          assigned={skills.data.skills}
          version={skills.data.version}
          onOpenChange={setAssigning}
        />
      )}
    </section>
  )
}
