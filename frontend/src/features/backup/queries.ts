import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type BackupRun = Schemas['BackupRunOut']
export type Archive = Schemas['ArchiveOut']
export type ArchiveCheck = Schemas['ArchiveCheckOut']
export type ArchiveFigures = Schemas['FiguresOut']
export type RestoreAttempt = Schemas['RestoreAttemptOut']

export const backupKeys = {
  all: ['backups'] as const,
  runs: ['backups', 'runs'] as const,
  archives: ['backups', 'archives'] as const,
  restore: ['backups', 'restore'] as const,
}

export function useBackupRuns() {
  return usePaged(
    pagedQuery(backupKeys.runs, async (cursor) =>
      unwrap(await api.GET('/api/backups', { params: { query: { cursor } } })),
    ),
  )
}

export function useArchives() {
  return usePaged(
    pagedQuery(backupKeys.archives, async (cursor) =>
      unwrap(await api.GET('/api/backups/archives', { params: { query: { cursor } } })),
    ),
  )
}

export const restoreStatusQuery = queryOptions({
  queryKey: backupKeys.restore,
  queryFn: async () => unwrap(await api.GET('/api/backups/restore')).attempt ?? null,
})

/** The last attempt to replace the installation from here (null: none yet). */
export function useRestoreStatus() {
  return useQuery(restoreStatusQuery)
}

/** "Jetzt sichern": a worker makes the backup; `backup.changed` reloads the lists. */
export function useStartBackup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/backups')),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: backupKeys.all }),
  })
}

/** An archive from elsewhere, as the raw request body. */
export function useUploadArchive() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST('/api/backups/archives', {
          body: file as unknown as string,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { 'Content-Type': 'application/x-tar' },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: backupKeys.archives }),
  })
}

export function useCheckArchive() {
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(await api.POST('/api/backups/archives/{name}/check', { params: { path: { name } } })),
  })
}

/** Replace the whole installation; the organisation's name is the confirmation. */
export function useReplaceInstallation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ name, confirm }: { name: string; confirm: string }) =>
      unwrap(
        await api.POST('/api/backups/archives/{name}/replace', {
          params: { path: { name } },
          body: { confirm },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: backupKeys.all }),
  })
}

/** Downloads are plain links (GET needs no CSRF header); the browser saves the file. */
export function archiveDownloadUrl(name: string): string {
  return `/api/backups/archives/${encodeURIComponent(name)}`
}
