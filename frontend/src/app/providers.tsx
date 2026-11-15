import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import type { ReactNode } from 'react'

const THEME_STORAGE_KEY = 'herd.theme'

export function Providers({
  queryClient,
  children,
}: {
  queryClient: QueryClient
  children: ReactNode
}) {
  return (
    <ThemeProvider
      // In a client-rendered app the anti-flash script never runs; as a data block React
      // leaves it alone instead of warning about a script tag.
      scriptProps={{ type: 'application/json' }}
      attribute="class"
      defaultTheme="system"
      enableSystem
      storageKey={THEME_STORAGE_KEY}
    >
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  )
}
