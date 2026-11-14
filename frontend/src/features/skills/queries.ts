import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Skill = Schemas['SkillOut']
export type SkillDetail = Schemas['SkillDetailOut']
export type SkillVersion = Schemas['SkillVersionOut']
export type SkillImport = Schemas['SkillImportOut']

/** Which skills a list shows: of one space, only organisation-wide, or all one sees. */
export interface SkillFilter {
  spaceId?: string
  orgWide?: boolean
  state?: Schemas['SkillState']
  q?: string
}

export const skillKeys = {
  all: ['skills'] as const,
  list: (filter: SkillFilter) => ['skills', 'list', filter] as const,
  detail: (id: string) => ['skills', 'detail', id] as const,
  versions: (id: string) => ['skills', 'versions', id] as const,
  version: (id: string, number: number) => ['skills', 'version', id, number] as const,
}

export const skillsQuery = (filter: SkillFilter) =>
  pagedQuery(skillKeys.list(filter), async (cursor) =>
    unwrap(
      await api.GET('/api/skills', {
        params: {
          query: {
            cursor,
            space_id: filter.spaceId,
            org_wide: filter.orgWide,
            state: filter.state,
            q: filter.q || undefined,
          },
        },
      }),
    ),
  )

export function useSkills(filter: SkillFilter, enabled = true) {
  return usePaged({ ...skillsQuery(filter), enabled })
}

export const skillQuery = (skillId: string) =>
  queryOptions({
    queryKey: skillKeys.detail(skillId),
    queryFn: async () =>
      unwrap(await api.GET('/api/skills/{skill_id}', { params: { path: { skill_id: skillId } } })),
  })

export function useSkill(skillId: string) {
  return useQuery(skillQuery(skillId))
}

export function useSkillVersions(skillId: string) {
  return usePaged(
    pagedQuery(skillKeys.versions(skillId), async (cursor) =>
      unwrap(
        await api.GET('/api/skills/{skill_id}/versions', {
          params: { path: { skill_id: skillId }, query: { cursor } },
        }),
      ),
    ),
  )
}

export function useSkillVersion(skillId: string, number: number | null) {
  return useQuery({
    queryKey: skillKeys.version(skillId, number ?? 0),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/skills/{skill_id}/versions/{number}', {
          params: { path: { skill_id: skillId, number: number ?? 0 } },
        }),
      ),
    enabled: number !== null,
  })
}

/** After any change: the skill, its versions and every list (and agents' skill sets). */
function useRefreshSkills() {
  const queryClient = useQueryClient()
  return (skill?: SkillDetail | Skill) => {
    if (skill && 'content' in skill) queryClient.setQueryData(skillKeys.detail(skill.id), skill)
    void queryClient.invalidateQueries({ queryKey: skillKeys.all })
    void queryClient.invalidateQueries({ queryKey: ['agents', 'detail'] })
  }
}

export function useCreateSkill() {
  const refresh = useRefreshSkills()
  return useMutation({
    mutationFn: async (body: Schemas['SkillCreate']) =>
      unwrap(await api.POST('/api/skills', { body })),
    onSuccess: refresh,
  })
}

export function useUpdateSkill(skillId: string) {
  const refresh = useRefreshSkills()
  return useMutation({
    mutationFn: async (body: Schemas['SkillUpdate']) =>
      unwrap(
        await api.PATCH('/api/skills/{skill_id}', {
          params: { path: { skill_id: skillId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

export function useArchiveSkill(skillId: string) {
  const refresh = useRefreshSkills()
  return useMutation({
    mutationFn: async ({ archive, version }: { archive: boolean; version: number }) => {
      const path = { skill_id: skillId }
      const body = { version }
      return unwrap(
        archive
          ? await api.POST('/api/skills/{skill_id}/archive', { params: { path }, body })
          : await api.POST('/api/skills/{skill_id}/unarchive', { params: { path }, body }),
      )
    },
    onSuccess: refresh,
  })
}

export function useRestoreSkillVersion(skillId: string) {
  const refresh = useRefreshSkills()
  return useMutation({
    mutationFn: async ({ number, version }: { number: number; version: number }) =>
      unwrap(
        await api.POST('/api/skills/{skill_id}/versions/{number}/restore', {
          params: { path: { skill_id: skillId, number } },
          body: { version },
        }),
      ),
    onSuccess: refresh,
  })
}

/** A SKILL.md or a ZIP of skill folders as the raw body, into a space or the
 *  organisation; nothing in it is ever run. */
export function useImportSkills(spaceId: string | null) {
  const refresh = useRefreshSkills()
  return useMutation({
    mutationFn: async (file: File) => {
      const zip = /\.zip$/i.test(file.name)
      return unwrap(
        await api.POST('/api/skills/import', {
          params: { query: { space_id: spaceId ?? undefined } },
          body: file as unknown as never,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { 'Content-Type': zip ? 'application/zip' : 'text/markdown' },
        }),
      )
    },
    onSuccess: () => refresh(),
  })
}

/** Downloads are plain links (GET needs no CSRF header). */
export function skillExportUrl(skillId: string): string {
  return `/api/skills/${encodeURIComponent(skillId)}/export`
}

/** The i18n key of an import's skip reason (`name_mismatch` → `nameMismatch`). */
export function reasonKey(reason: string): string {
  return reason.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase())
}
