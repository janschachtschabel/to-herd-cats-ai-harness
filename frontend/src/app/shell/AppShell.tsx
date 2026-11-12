import { PanelLeft } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Sidebar } from './Sidebar'
import { UserMenu } from './UserMenu'

/** Sidebar on the left, header with the user menu, the page in the middle. */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(true)
  return (
    <div className="flex h-dvh w-full bg-background text-foreground">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow"
      >
        {t('nav.skipToContent')}
      </a>
      <aside
        id="sidebar"
        className={cn(
          'flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground',
          open ? 'w-64' : 'hidden',
        )}
      >
        <Sidebar />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t('nav.toggleSidebar')}
            aria-controls="sidebar"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <PanelLeft aria-hidden />
          </Button>
          <div className="ml-auto">
            <UserMenu />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="min-h-0 flex-1 overflow-y-auto focus:outline-none">
          <div className="mx-auto w-full max-w-5xl px-6 py-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
