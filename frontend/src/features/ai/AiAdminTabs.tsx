import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

// `exact: false`: the tab stays marked on its pages below (one server's page).
const TABS = [
  { to: '/admin/ai', labelKey: 'ai.tabs.connections', exact: true },
  { to: '/admin/ai/assignments', labelKey: 'ai.tabs.assignments', exact: true },
  { to: '/admin/ai/usage', labelKey: 'ai.tabs.usage', exact: true },
  { to: '/admin/ai/budgets', labelKey: 'ai.tabs.budgets', exact: true },
  { to: '/admin/ai/mcp', labelKey: 'ai.tabs.mcp', exact: true },
  { to: '/admin/ai/mcp-servers', labelKey: 'ai.tabs.mcpServers', exact: false },
  { to: '/admin/ai/connectors', labelKey: 'ai.tabs.connectors', exact: true },
  { to: '/admin/ai/catalog', labelKey: 'ai.tabs.catalog', exact: true },
] as const

/** The pages of the AI administration, as links (the current one marked). */
export function AiAdminTabs() {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('ai.tabs.label')} className="mb-6 flex flex-wrap gap-1 border-b">
      {TABS.map((tab) => (
        <Link
          key={tab.to}
          to={tab.to}
          activeOptions={{ exact: tab.exact }}
          className="-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[status=active]:border-primary data-[status=active]:font-medium data-[status=active]:text-foreground"
        >
          {t(tab.labelKey)}
        </Link>
      ))}
    </nav>
  )
}
