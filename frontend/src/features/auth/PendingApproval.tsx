import { Link } from '@tanstack/react-router'
import { Hourglass } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/** Where a self-registration (and every sign-in until then) ends: the account exists
 *  but waits for an administrator's approval (`oidc.account_pending`). */
export function PendingApproval() {
  const { t } = useTranslation()
  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <Hourglass aria-hidden className="mb-2 size-6 text-muted-foreground" />
        <CardTitle>
          <h1 className="text-lg font-semibold">{t('signin.pending.title')}</h1>
        </CardTitle>
        <CardDescription>{t('signin.pending.text')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm text-muted-foreground">
        <p>{t('signin.pending.next')}</p>
        <Link to="/login" search={{}} className={buttonVariants({ variant: 'outline' })}>
          {t('signin.pending.back')}
        </Link>
      </CardContent>
    </Card>
  )
}
