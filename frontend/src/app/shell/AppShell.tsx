import { PanelLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { LocaleError } from '@/features/profile/LocaleError'
import { useUserLocale } from '@/features/profile/queries'
import { SearchProvider } from '@/features/search/SearchProvider'
import { cn } from '@/lib/utils'
import { LiveHint } from './LiveStatus'
import { Sidebar } from './Sidebar'
import { useShellLive } from './useShellLive'
import { useSidebar } from './useSidebar'
import { UserMenu } from './UserMenu'

/** Sidebar on the left (over the page on a narrow screen), header with the user menu,
 *  the page in the middle. */
export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { open, narrow, toggle, close, onSidebarClick } = useSidebar()
  useUserLocale()
  useShellLive()
  return (
    <SearchProvider>
      <div className="flex h-dvh w-full bg-background text-foreground">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow"
        >
          {t('nav.skipToContent')}
        </a>
        {narrow && open && (
          // A click beside the open sidebar closes it (Escape does too).
          <div className="fixed inset-0 z-30 bg-black/40" aria-hidden onClick={close} />
        )}
        <aside
          id="sidebar"
          hidden={!open}
          onClick={onSidebarClick}
          className={cn(
            'flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground',
            open ? 'w-64' : 'hidden',
            narrow && 'fixed inset-y-0 left-0 z-40 max-w-[85vw] shadow-lg',
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
              onClick={toggle}
            >
              <PanelLeft aria-hidden />
            </Button>
            <div className="ml-auto flex items-center gap-3">
              <LiveHint />
              <UserMenu />
            </div>
          </header>
          <main
            id="main"
            tabIndex={-1}
            className="min-h-0 flex-1 overflow-y-auto focus:outline-none"
          >
            <div className="mx-auto w-full max-w-5xl px-6 py-8">
              <LocaleError />
              {children}
            </div>
          </main>
        </div>
      </div>
    </SearchProvider>
  )
}
