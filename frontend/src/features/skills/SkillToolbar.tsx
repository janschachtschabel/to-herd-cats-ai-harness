import { Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'

type State = Schemas['SkillState']

/** The filters above a skill list: a search by name, the state, and optionally where
 *  the skills belong (`children`). */
export function SkillToolbar({
  search,
  state,
  onSearch,
  onState,
  children,
}: {
  search: string
  state: State
  onSearch: (search: string) => void
  onState: (state: State) => void
  children?: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_minmax(0,12rem)]">
      <Field label={t('skills.filter.search')}>
        {(props) => (
          <div className="relative">
            <Search
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              {...props}
              type="search"
              className="pl-8"
              maxLength={64}
              value={search}
              onChange={(e) => onSearch(e.target.value)}
            />
          </div>
        )}
      </Field>
      <Field label={t('skills.filter.state')}>
        {(props) => (
          <NativeSelect {...props} value={state} onChange={(e) => onState(e.target.value as State)}>
            <option value="active">{t('skills.state.active')}</option>
            <option value="archived">{t('skills.state.archived')}</option>
          </NativeSelect>
        )}
      </Field>
      {children}
    </div>
  )
}
