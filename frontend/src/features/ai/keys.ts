/** The query keys of the AI administration. Every key starts with `ai`. */
export const aiKeys = {
  all: ['ai'] as const,
  connections: ['ai', 'connections'] as const,
  connection: (id: string) => ['ai', 'connection', id] as const,
  assignments: ['ai', 'assignments'] as const,
  groupAssignments: ['ai', 'assignments', 'groups'] as const,
  userAssignments: ['ai', 'assignments', 'users'] as const,
  usage: (by: string, from: string, to: string) => ['ai', 'usage', by, from, to] as const,
  myUsage: ['ai', 'usage', 'me'] as const,
}
