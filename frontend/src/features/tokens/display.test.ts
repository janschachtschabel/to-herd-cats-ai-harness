import { describe, expect, test } from 'vitest'
import { connectSnippets, mcpUrl, scopeNames, tokenState } from './display'

const NOW = new Date('2026-11-15T12:00:00Z')

describe('tokens in words', () => {
  test('revoked wins over expired; a token past its expiry is expired', () => {
    const later = '2026-12-01T00:00:00Z'
    const earlier = '2026-11-01T00:00:00Z'
    expect(tokenState({ expires_at: later, revoked_at: null }, NOW)).toBe('active')
    expect(tokenState({ expires_at: earlier, revoked_at: null }, NOW)).toBe('expired')
    expect(tokenState({ expires_at: earlier, revoked_at: earlier }, NOW)).toBe('revoked')
  })

  test('the endpoint is the app origin with /mcp; the token stays in a variable', () => {
    expect(mcpUrl('https://herd.example.com/')).toBe('https://herd.example.com/mcp')
    const mine = connectSnippets('https://herd.example.com', false)
    expect(mine.claude).toBe(
      'claude mcp add --transport http herd https://herd.example.com/mcp \\\n' +
        '  --header "Authorization: Bearer $HERD_TOKEN"',
    )
    expect(mine.codex).toContain('bearer_token_env_var = "HERD_TOKEN"')
    expect(connectSnippets('https://h.example', true).claude).toContain('$HERD_AGENT_TOKEN')
  })

  test('spaces are named where known and counted where not', () => {
    const names = new Map([['a', 'Vertrieb']])
    expect(scopeNames(null, names)).toEqual({ all: true })
    expect(scopeNames(['a', 'b'], names)).toEqual({ all: false, named: ['Vertrieb'], unnamed: 1 })
  })
})
