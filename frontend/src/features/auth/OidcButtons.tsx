import { KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { signInHref, useSignInProviders, type SignInProvider } from './queries'
import { useSignInError } from './signInError'

/** Google's "G" in its four colours (inline, no third-party request). */
function GoogleMark() {
  return (
    <svg aria-hidden viewBox="0 0 48 48" className="size-4">
      <path
        fill="#EA4335"
        d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 7l7.2 5.6c4.2-3.9 7.1-9.6 7.1-17.1z"
      />
      <path
        fill="#FBBC05"
        d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.2-5.6c-2.2 1.5-5.1 2.4-8.7 2.4-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"
      />
    </svg>
  )
}

/** The mark beside a provider's name: Google's "G", a key for any other. */
export function ProviderIcon({ kind }: { kind: SignInProvider['kind'] }) {
  return kind === 'google' ? <GoogleMark /> : <KeyRound aria-hidden className="size-4" />
}

function ProviderButton({ provider }: { provider: SignInProvider }) {
  const { t } = useTranslation()
  const google = provider.kind === 'google'
  return (
    <a
      href={signInHref(provider.key)}
      className={cn(buttonVariants({ variant: 'outline' }), 'w-full justify-center gap-2')}
    >
      <ProviderIcon kind={provider.kind} />
      {google ? t('signin.withGoogle') : t('signin.with', { name: provider.name })}
    </a>
  )
}

/** One button per enabled provider, then the divider to the password form; nothing
 *  without providers. */
export function OidcButtons({ error }: { error?: string }) {
  const { t } = useTranslation()
  const providers = useSignInProviders()
  const message = useSignInError(error)
  return (
    <>
      {message && (
        <Alert variant="destructive">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {providers.length > 0 && (
        <div className="flex flex-col gap-2">
          {providers.map((provider) => (
            <ProviderButton key={provider.key} provider={provider} />
          ))}
          <div className="flex items-center gap-3 pt-2 text-xs text-muted-foreground">
            <span aria-hidden className="h-px flex-1 bg-border" />
            {t('signin.or')}
            <span aria-hidden className="h-px flex-1 bg-border" />
          </div>
        </div>
      )}
    </>
  )
}
