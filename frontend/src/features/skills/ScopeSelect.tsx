import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import type { Space } from '@/lib/api'
import type { Scope } from './scope'

/** Where skills belong: the organisation or one of `spaces` (and, for filtering,
 *  everywhere). */
export function ScopeSelect({
  label,
  value,
  spaces,
  withAll = false,
  onChange,
}: {
  label: string
  value: Scope
  spaces: readonly Space[]
  withAll?: boolean
  onChange: (scope: Scope) => void
}) {
  const { t } = useTranslation()
  return (
    <Field label={label}>
      {(props) => (
        <NativeSelect {...props} value={value} onChange={(e) => onChange(e.target.value)}>
          {withAll && <option value="all">{t('skills.scope.all')}</option>}
          <option value="org">{t('skills.scope.org')}</option>
          {spaces.map((space) => (
            <option key={space.id} value={space.id}>
              {space.name}
            </option>
          ))}
        </NativeSelect>
      )}
    </Field>
  )
}
