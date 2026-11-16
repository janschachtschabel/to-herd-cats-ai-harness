import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'

export type TotpStatus = Schemas['TotpStatusOut']

export const totpQuery = queryOptions({
  queryKey: ['auth', 'me', 'totp'],
  queryFn: async (): Promise<TotpStatus> => unwrap(await api.GET('/api/auth/me/totp')),
})

/** Whether the person has TOTP on, and why it cannot be set up if it cannot. */
export function useTotpStatus() {
  return useQuery(totpQuery)
}

function useRefreshTotp() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: totpQuery.queryKey })
}

/** A new secret (shown once); the current password proves it is the person. */
export function useStartTotp() {
  return useMutation({
    mutationFn: async (password: string) =>
      unwrap(await api.POST('/api/auth/me/totp/setup', { body: { password } })),
  })
}

/** The first code turns TOTP on; the answer holds the recovery codes, shown once. */
export function useConfirmTotp() {
  const refresh = useRefreshTotp()
  return useMutation({
    mutationFn: async (code: string) =>
      unwrap(await api.POST('/api/auth/me/totp/confirm', { body: { code } })).recovery_codes,
    onSuccess: () => void refresh(),
  })
}

export function useDisableTotp() {
  const refresh = useRefreshTotp()
  return useMutation({
    mutationFn: async (body: Schemas['SecondFactorIn']) =>
      unwrap(await api.POST('/api/auth/me/totp/disable', { body })),
    onSuccess: () => void refresh(),
  })
}

export function useRenewRecoveryCodes() {
  const refresh = useRefreshTotp()
  return useMutation({
    mutationFn: async (code: string) =>
      unwrap(await api.POST('/api/auth/me/totp/recovery-codes', { body: { code } })).recovery_codes,
    onSuccess: () => void refresh(),
  })
}

/** What the person typed: six digits are a code, anything else a recovery code. */
export function proofOf(typed: string): Schemas['SecondFactorIn'] {
  const value = typed.trim()
  return /^\d[\d ]*$/.test(value) ? { code: value } : { recovery_code: value }
}
