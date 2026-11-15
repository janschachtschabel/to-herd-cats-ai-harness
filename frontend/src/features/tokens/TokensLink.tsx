import { Link } from '@tanstack/react-router'
import { KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { hasPermission, useMe } from '@/features/auth/queries'

/** On the personal settings: where one's access tokens for AI clients are (only with
 *  `mcp.use`; everyone else sees nothing of the feature). */
export function TokensLink() {
  const { t } = useTranslation()
  const me = useMe()
  if (!hasPermission(me, 'mcp.use')) return null
  return (
    <section aria-labelledby="profile-tokens" className="mt-8 flex flex-col gap-2 border-t pt-6">
      <h2 id="profile-tokens" className="text-base font-semibold">
        {t('tokens.profile.title')}
      </h2>
      <p className="text-sm text-muted-foreground">{t('tokens.profile.text')}</p>
      <div>
        <Button variant="outline" asChild>
          <Link to="/profile/tokens">
            <KeyRound aria-hidden />
            {t('tokens.profile.open')}
          </Link>
        </Button>
      </div>
    </section>
  )
}
