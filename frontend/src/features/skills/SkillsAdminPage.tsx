import { Plus, Upload } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/features/shared/states'
import { useSpaces } from '@/features/spaces/queries'
import type { Schemas } from '@/lib/api'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { ImportSkillsDialog } from './ImportSkillsDialog'
import { scopeFilter, targetSpace, type Scope } from './scope'
import { ScopeSelect } from './ScopeSelect'
import { SkillFormDialog } from './SkillFormDialog'
import { SkillList } from './SkillList'
import { SkillToolbar } from './SkillToolbar'

/** Every skill of the organisation (`skill.manage`): organisation-wide and per space,
 *  filtered and searched; create and import anywhere. */
export function SkillsAdminPage() {
  const { t } = useTranslation()
  const spaces = useSpaces()
  const [scope, setScope] = useState<Scope>('all')
  const [state, setState] = useState<Schemas['SkillState']>('active')
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search.trim(), 300)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [target, setTarget] = useState<Scope>('org')
  const names = useMemo(() => new Map(spaces.items.map((s) => [s.id, s.name])), [spaces.items])

  const open = (setOpen: (open: boolean) => void) => {
    setTarget(targetSpace(scope) ?? 'org')
    setOpen(true)
  }
  const where = (
    <ScopeSelect
      label={t('skills.scope.target')}
      value={target}
      spaces={spaces.items}
      onChange={setTarget}
    />
  )

  return (
    <div>
      <PageHeader
        title={t('skills.title')}
        description={t('skills.description')}
        actions={
          <>
            <Button variant="outline" onClick={() => open(setImporting)}>
              <Upload aria-hidden />
              {t('skills.import.open')}
            </Button>
            <Button onClick={() => open(setCreating)}>
              <Plus aria-hidden />
              {t('skills.create.open')}
            </Button>
          </>
        }
      />
      <SkillToolbar search={search} state={state} onSearch={setSearch} onState={setState}>
        <ScopeSelect
          label={t('skills.scope.filter')}
          value={scope}
          spaces={spaces.items}
          withAll
          onChange={setScope}
        />
      </SkillToolbar>
      <SkillList filter={{ ...scopeFilter(scope), state, q }} spaceNames={names} />
      <SkillFormDialog
        open={creating}
        spaceId={targetSpace(target)}
        where={where}
        onOpenChange={setCreating}
      />
      <ImportSkillsDialog
        open={importing}
        spaceId={targetSpace(target)}
        where={where}
        onOpenChange={setImporting}
      />
    </div>
  )
}
