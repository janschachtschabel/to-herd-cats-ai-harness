import { useMutation, useMutationState, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { meQuery, useMe } from '@/features/auth/queries'
import { api, ApiError, unwrap, type Me, type Schemas } from '@/lib/api'
import { setLocale, type Locale } from '@/lib/i18n'

const localeKey = ['auth', 'me', 'locale'] as const

/** `me` as the server has it now (after a change that moved the person's version). */
export function useRefreshMe() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: meQuery.queryKey, exact: true })
}

/** Switches the interface language at once and stores it for the person. A version
 *  conflict (a change elsewhere: another tab, an administrator) reads `me` again and
 *  stores once more; if storing still fails, the previous language comes back and
 *  `useLocaleError` holds the error. */
export function useChangeLocale() {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationKey: localeKey,
    mutationFn: async ({ locale, version }: { locale: Locale; version: number }) => {
      const store = async (v: number) =>
        unwrap(await api.PATCH('/api/auth/me', { body: { locale, version: v } }))
      try {
        return await store(version)
      } catch (error) {
        if (!(error instanceof ApiError && error.isVersionConflict)) throw error
        const fresh = await queryClient.fetchQuery({ ...meQuery, staleTime: 0 })
        if (!fresh) throw error
        return await store(fresh.user.version)
      }
    },
    onSuccess: (me: Me) => queryClient.setQueryData(meQuery.queryKey, me),
  })
  return (locale: Locale) => {
    const me = queryClient.getQueryData(meQuery.queryKey)
    if (!me) return
    const previous = me.user.locale as Locale
    setLocale(locale)
    mutation.mutate({ locale, version: me.user.version }, { onError: () => setLocale(previous) })
  }
}

/** The error of the latest language change, if it failed, and a way to dismiss it. */
export function useLocaleError(): { error: unknown; dismiss: () => void } {
  const queryClient = useQueryClient()
  const states = useMutationState({ filters: { mutationKey: localeKey } })
  const latest = states.at(-1)
  const dismiss = () => {
    const cache = queryClient.getMutationCache()
    for (const mutation of cache.findAll({ mutationKey: localeKey })) cache.remove(mutation)
  }
  return { error: latest?.status === 'error' ? latest.error : null, dismiss }
}

/** The interface speaks the language stored for the person logged in. */
export function useUserLocale() {
  const locale = useMe()?.user.locale
  useEffect(() => {
    if (locale === 'de' || locale === 'en') setLocale(locale)
  }, [locale])
}

/** Changes the caller's own password; the server ends every other session and moves
 *  the person's version, so `me` is read again. */
export function useChangePassword() {
  const refreshMe = useRefreshMe()
  return useMutation({
    mutationFn: async (body: Schemas['PasswordChangeIn']) =>
      unwrap(await api.POST('/api/auth/me/password', { body })),
    onSuccess: () => refreshMe(),
  })
}
