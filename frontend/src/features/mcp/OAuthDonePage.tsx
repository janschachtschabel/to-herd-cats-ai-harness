import { Link } from '@tanstack/react-router'
import { CircleCheck, CircleX } from 'lucide-react'
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { hasPermission, useMe } from '@/features/auth/queries'
import { cn } from '@/lib/utils'
import type { OAuthStatus } from './display'
import { mcpKeys } from './keys'

/** Where the browser lands after the provider's sign-in (`/ai/oauth/done?status=…`):
 *  connected, or why not (declined at the provider, failed, or an expired or reused
 *  sign-in), in words; then back to one's connections or the connectors. The
 *  connector lists are read again, so they show the new state. */
export function OAuthDonePage({ status }: { status: OAuthStatus }) {
  const { t } = useTranslation()
  const me = useMe()
  const queryClient = useQueryClient()
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: mcpKeys.all })
  }, [queryClient])
  const ok = status === 'connected'
  const Icon = ok ? CircleCheck : CircleX
  return (
    <div className="mx-auto mt-10 flex max-w-lg flex-col items-center gap-4 text-center">
      <Icon
        className={cn(
          'size-12',
          ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400',
        )}
        aria-hidden
      />
      <h1 className="text-xl font-semibold tracking-tight">{t(`mcp.oauthDone.${status}.title`)}</h1>
      <p role={ok ? 'status' : 'alert'} className="text-sm text-muted-foreground">
        {t(`mcp.oauthDone.${status}.text`)}
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {hasPermission(me, 'ai.use') && (
          <Button asChild>
            <Link to="/my-connections">{t('mcp.oauthDone.toMine')}</Link>
          </Button>
        )}
        {hasPermission(me, 'ai.manage') && (
          <Button variant="outline" asChild>
            <Link to="/admin/ai/connectors">{t('mcp.oauthDone.toShared')}</Link>
          </Button>
        )}
      </div>
    </div>
  )
}
