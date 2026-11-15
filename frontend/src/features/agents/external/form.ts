import type { Schemas } from '@/lib/api'

/** The levels an external agent can have (plan M8 decision 11: it proposes at most). */
export const EXTERNAL_LEVELS = [1, 2] as const

/** An external agent's form: what it is made with; `level` only when creating. */
export interface ExternalValues {
  name: string
  intro: string
  responsible_user_id: string
  status: Schemas['AgentStatus']
  level: '1' | '2'
}

export function createBody(values: ExternalValues): Schemas['AgentCreate'] {
  return {
    kind: 'external',
    name: values.name,
    intro: values.intro,
    responsible_user_id: values.responsible_user_id,
    status: values.status,
    level: Number(values.level),
  }
}

export function updateBody(values: ExternalValues, version: number): Schemas['AgentUpdate'] {
  return {
    name: values.name,
    intro: values.intro,
    responsible_user_id: values.responsible_user_id,
    status: values.status,
    version,
  }
}
