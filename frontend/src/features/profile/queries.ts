import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { meQuery, useMe } from '@/features/auth/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { setLocale, type Locale } from '@/lib/i18n'

/** Changes the caller's own settings; the answer is the new `me`. */
export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Schemas['ProfileUpdateIn']) =>
      unwrap(await api.PATCH('/api/auth/me', { body })),
    onSuccess: (me) => queryClient.setQueryData(meQuery.queryKey, me),
  })
}

/** Switches the interface language at once and stores it for the person; if storing
 *  fails, the stored language comes back. */
export function useChangeLocale() {
  const me = useMe()
  const update = useUpdateProfile()
  return (locale: Locale) => {
    if (!me) return
    setLocale(locale)
    update.mutate(
      { locale, version: me.user.version },
      { onError: () => setLocale(me.user.locale as Locale) },
    )
  }
}

/** The interface speaks the language stored for the person logged in. */
export function useUserLocale() {
  const locale = useMe()?.user.locale
  useEffect(() => {
    if (locale === 'de' || locale === 'en') setLocale(locale)
  }, [locale])
}
