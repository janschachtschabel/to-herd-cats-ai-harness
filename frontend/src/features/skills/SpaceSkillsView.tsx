import { Plus, Upload } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import type { Schemas } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { skillAbilities } from './abilities'
import { ImportSkillsDialog } from './ImportSkillsDialog'
import { SkillFormDialog } from './SkillFormDialog'
import { SkillList } from './SkillList'
import { SkillToolbar } from './SkillToolbar'

/** A space's skills: everyone with AI and a role here reads them; moderators with AI
 *  (and `skill.manage`) create and import them. */
export function SpaceSkillsView() {
  const { t } = useTranslation()
  const { space, me } = useWiki()
  const abilities = skillAbilities(me, space)
  const [state, setState] = useState<Schemas['SkillState']>('active')
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search.trim(), 300)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)

  if (!abilities.read) return <EmptyState text={t('skills.noAccess')} />
  return (
    <section aria-labelledby="space-skills">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="space-skills" className="text-lg font-semibold">
            {t('skills.spaceTitle')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('skills.spaceDescription')}</p>
        </div>
        {abilities.manage && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setImporting(true)}>
              <Upload aria-hidden />
              {t('skills.import.open')}
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden />
              {t('skills.create.open')}
            </Button>
          </div>
        )}
      </div>
      <SkillToolbar search={search} state={state} onSearch={setSearch} onState={setState} />
      <SkillList
        filter={{ spaceId: space.id, state, q }}
        spaceNames={new Map([[space.id, space.name]])}
      />
      {abilities.manage && (
        <>
          <SkillFormDialog open={creating} spaceId={space.id} onOpenChange={setCreating} />
          <ImportSkillsDialog open={importing} spaceId={space.id} onOpenChange={setImporting} />
        </>
      )}
    </section>
  )
}
