import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import type { TreeItem } from './tree'

const TOP = ''

/** A page picker in tree order (indented); the empty value is "top level". */
export function PageParentSelect({
  options,
  value,
  onChange,
  ...props
}: {
  options: { node: TreeItem; depth: number }[]
  value: string | null
  onChange: (value: string | null) => void
  id?: string
  'aria-invalid'?: boolean
  'aria-describedby'?: string
}) {
  const { t } = useTranslation()
  return (
    <NativeSelect
      {...props}
      value={value ?? TOP}
      onChange={(event) => onChange(event.target.value === TOP ? null : event.target.value)}
    >
      <option value={TOP}>{t('wiki.parent.top')}</option>
      {options.map(({ node, depth }) => (
        <option key={node.id} value={node.id}>
          {'  '.repeat(depth + 1) + node.title}
        </option>
      ))}
    </NativeSelect>
  )
}
