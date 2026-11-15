import type { Schemas } from '@/lib/api'

type TokenFacts = Pick<Schemas['TokenOut'], 'expires_at' | 'revoked_at'>

/** Where a token stands: in use, past its expiry, or revoked (revoked wins). */
export type TokenState = 'active' | 'expired' | 'revoked'

export function tokenState(token: TokenFacts, now: Date): TokenState {
  if (token.revoked_at) return 'revoked'
  return new Date(token.expires_at) <= now ? 'expired' : 'active'
}

/** The longest a token may live (the API refuses more). */
export const MAX_EXPIRY_DAYS = 365
export const DEFAULT_EXPIRY_DAYS = 90

/** The environment variable a client reads the token from (`docs/MCP.md`): a person's
 *  own client, or the machine an external agent runs on. */
export function tokenVariable(forAgent: boolean): string {
  return forAgent ? 'HERD_AGENT_TOKEN' : 'HERD_TOKEN'
}

/** The address of the MCP endpoint on this installation (the app's own origin). */
export function mcpUrl(origin: string): string {
  return `${origin.replace(/\/+$/, '')}/mcp`
}

/** How to connect Claude Code and Codex: the token never goes into the command or a
 *  file, only into the environment variable the client reads (`docs/MCP.md`). */
export function connectSnippets(origin: string, forAgent: boolean) {
  const url = mcpUrl(origin)
  const variable = tokenVariable(forAgent)
  return {
    claude: `claude mcp add --transport http herd ${url} \\\n  --header "Authorization: Bearer $${variable}"`,
    codex: `[mcp_servers.herd]\nurl = "${url}"\nbearer_token_env_var = "${variable}"`,
  }
}

/** The spaces of a token in words: all of the owner's, or the names known here (a space
 *  the reader cannot see is counted, never named). */
export function scopeNames(
  spaceIds: readonly string[] | null,
  names: ReadonlyMap<string, string>,
): { all: true } | { all: false; named: string[]; unnamed: number } {
  if (spaceIds === null) return { all: true }
  const named = spaceIds.flatMap((id) => {
    const name = names.get(id)
    return name ? [name] : []
  })
  return { all: false, named, unnamed: spaceIds.length - named.length }
}
