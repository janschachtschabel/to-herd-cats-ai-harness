import { Wrench } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { reload, useMaintenanceShown, useMaintenanceState } from './maintenance'

/** The whole window while the installation is in maintenance (plan M9 decision 9). It
 *  asks every few seconds; once maintenance has ended the app starts again from `/`
 *  (after a replace nobody is signed in any more, so that is the login). */
export function MaintenancePage() {
  const { t } = useTranslation()
  const state = useMaintenanceState(true)
  // Only an answer asked for here counts, never one remembered from before.
  const active = state.isFetchedAfterMount ? state.data?.active : undefined
  useEffect(() => {
    if (active === false) reload.to('/')
  }, [active])
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6 text-foreground">
      <div className="max-w-md text-center" role="status" aria-live="polite">
        <Wrench className="mx-auto mb-4 size-10 text-muted-foreground" aria-hidden />
        <h1 className="text-xl font-semibold tracking-tight">{t('maintenance.title')}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t('maintenance.text')}</p>
        <p className="mt-4 text-xs text-muted-foreground">{t('maintenance.checking')}</p>
      </div>
    </main>
  )
}

/** The app, or the maintenance page once a request met maintenance. */
export function MaintenanceGate({ children }: { children: ReactNode }) {
  return useMaintenanceShown() ? <MaintenancePage /> : <>{children}</>
}
