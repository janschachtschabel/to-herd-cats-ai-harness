import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

const TABS = [
  { to: '/admin/ai', labelKey: 'ai.tabs.connections' },
  { to: '/admin/ai/assignments', labelKey: 'ai.tabs.assignments' },
  { to: '/admin/ai/usage', labelKey: 'ai.tabs.usage' },
] as const

/** The three pages of the AI administration, as links (the current one marked). */
export function AiAdminTabs() {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('ai.tabs.label')} className="mb-6 flex flex-wrap gap-1 border-b">
      {TABS.map((tab) => (
        <Link
          key={tab.to}
          to={tab.to}
          activeOptions={{ exact: true }}
          className="-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[status=active]:border-primary data-[status=active]:font-medium data-[status=active]:text-foreground"
        >
          {t(tab.labelKey)}
        </Link>
      ))}
    </nav>
  )
}
