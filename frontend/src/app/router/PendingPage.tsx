import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/features/shared/states'

/** A route whose page arrives with the next task: the shell and guards work already. */
export function PendingPage({
  titleKey,
}: {
  titleKey: 'spaces.title' | 'users.title' | 'groups.title' | 'audit.title'
}) {
  const { t } = useTranslation()
  return <PageHeader title={t(titleKey)} />
}
