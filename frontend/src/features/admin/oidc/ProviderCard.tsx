import { KeyRound, Pencil, ShieldCheck, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { cn } from '@/lib/utils'
import { Callback } from './Callback'
import {
  useCheckOidcProvider,
  useDeleteOidcProvider,
  useUpdateOidcProvider,
  type OidcProvider,
} from './queries'

/** One provider: what it is, where Google or the IdP sends people back, who may sign
 *  up, and what one can do with it. */
export function ProviderCard({ provider, onEdit }: { provider: OidcProvider; onEdit: () => void }) {
  const { t } = useTranslation()
  const check = useCheckOidcProvider()
  const toggle = useUpdateOidcProvider(provider.id)
  const remove = useDeleteOidcProvider()
  const [confirming, setConfirming] = useState(false)
  const failure = toggle.error ?? check.error
  const result = check.data

  return (
    <article
      aria-label={provider.name}
      className={cn('rounded-lg border p-4', !provider.enabled && 'bg-muted/40')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold break-words">{provider.name}</h2>
          <p className="text-xs break-all text-muted-foreground">{provider.issuer}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{t(`oidcAdmin.kinds.${provider.kind}`)}</Badge>
          <Badge variant="outline">
            {provider.discovered ? t('oidcAdmin.discovered') : t('oidcAdmin.notDiscovered')}
          </Badge>
          <Badge variant={provider.enabled ? 'secondary' : 'destructive'}>
            {provider.enabled ? t('oidcAdmin.status.on') : t('oidcAdmin.status.off')}
          </Badge>
        </div>
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">{t('oidcAdmin.form.clientId')}</dt>
        <dd className="break-all">{provider.client_id}</dd>
        <dt className="text-muted-foreground">{t('oidcAdmin.form.secret')}</dt>
        <dd className="inline-flex items-center gap-1">
          <KeyRound className="size-3.5 text-muted-foreground" aria-hidden />
          {provider.client_secret.set
            ? t(`oidcAdmin.secretKinds.${provider.client_secret.kind ?? 'enc'}`)
            : t('oidcAdmin.noSecret')}
        </dd>
        <dt className="text-muted-foreground">{t('oidcAdmin.signup')}</dt>
        <dd className="break-words">
          {provider.allow_signup
            ? t('oidcAdmin.signupFor', { domains: provider.allowed_domains.join(', ') })
            : t('oidcAdmin.signupOff')}
        </dd>
        <dt className="text-muted-foreground">{t('oidcAdmin.callback')}</dt>
        <dd className="min-w-0">
          <Callback url={provider.callback_url} />
        </dd>
      </dl>
      {result && (
        <p
          role="status"
          className={cn(
            'mt-3 text-sm',
            result.ok ? 'text-emerald-700 dark:text-emerald-400' : 'text-destructive',
          )}
        >
          {result.ok
            ? t('oidcAdmin.checkOk')
            : `${t('oidcAdmin.checkFailed')} ${t(`errors.${result.code ?? 'oidc.provider_error'}`)}`}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={check.isPending}
          onClick={() => check.mutate(provider.id)}
        >
          <ShieldCheck aria-hidden />
          {check.isPending ? t('oidcAdmin.checking') : t('oidcAdmin.check')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          aria-label={t('oidcAdmin.editNamed', { name: provider.name })}
          onClick={onEdit}
        >
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={toggle.isPending}
          onClick={() => toggle.mutate({ enabled: !provider.enabled, version: provider.version })}
        >
          {provider.enabled ? t('oidcAdmin.disable') : t('oidcAdmin.enable')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('oidcAdmin.deleteNamed', { name: provider.name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      {failure ? (
        <div className="mt-3">
          <SaveError error={failure} />
        </div>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title={t('oidcAdmin.deleteTitle')}
        text={t('oidcAdmin.deleteText', { name: provider.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() => remove.mutate(provider, { onSuccess: () => setConfirming(false) })}
      />
    </article>
  )
}
