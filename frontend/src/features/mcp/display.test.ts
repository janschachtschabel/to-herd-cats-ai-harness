import { describe, expect, test } from 'vitest'
import { makeConnector, makeTool } from '@/test/mcp'
import {
  connectorState,
  localized,
  remoteTone,
  safeAuthorizationUrl,
  toolNeedsAttention,
  toolView,
} from './display'

describe('the words of MCP servers and connectors', () => {
  test('a tool shows one state: missing wins, pending is new', () => {
    expect(toolView(makeTool({ state: 'pending' }))).toBe('new')
    expect(toolView(makeTool({ state: 'approved', approved_fingerprint: 'f1' }))).toBe('approved')
    expect(toolView(makeTool({ state: 'blocked' }))).toBe('blocked')
    expect(toolView(makeTool({ state: 'changed' }))).toBe('changed')
    expect(toolView(makeTool({ state: 'approved', missing: true }))).toBe('missing')
  })

  test('new and changed tools need the admin', () => {
    expect(toolNeedsAttention(makeTool({ state: 'pending' }))).toBe(true)
    expect(toolNeedsAttention(makeTool({ state: 'changed' }))).toBe(true)
    expect(toolNeedsAttention(makeTool({ state: 'approved' }))).toBe(false)
    expect(toolNeedsAttention(makeTool({ state: 'pending', missing: true }))).toBe(false)
  })

  test('a remote answer as a tone', () => {
    expect(remoteTone('ok')).toBe('ok')
    expect(remoteTone('unauthorized')).toBe('refused')
    expect(remoteTone('forbidden')).toBe('refused')
    expect(remoteTone('timeout')).toBe('failed')
    expect(remoteTone('blocked')).toBe('failed')
  })

  test('a connector is connected, not connected, or holds a key', () => {
    expect(connectorState(makeConnector({ auth_kind: 'oauth', has_secret: true }))).toBe(
      'connected',
    )
    expect(connectorState(makeConnector({ auth_kind: 'oauth', has_secret: false }))).toBe(
      'disconnected',
    )
    expect(connectorState(makeConnector({ auth_kind: 'bearer', secret_kind: 'env' }))).toBe('env')
    expect(connectorState(makeConnector({ auth_kind: 'header', secret_kind: 'enc' }))).toBe('enc')
  })

  test('a catalogue text in the reader’s language, German otherwise', () => {
    const text = { de: 'Hallo', en: 'Hello' }
    expect(localized(text, 'en')).toBe('Hello')
    expect(localized(text, 'de')).toBe('Hallo')
    expect(localized(text, 'fr')).toBe('Hallo')
    expect(localized(null, 'de')).toBe('')
  })

  test('the browser goes only to an https authorization address', () => {
    expect(safeAuthorizationUrl('https://gitlab.com/oauth/authorize?x=1')).toBe(
      'https://gitlab.com/oauth/authorize?x=1',
    )
    expect(safeAuthorizationUrl('javascript:alert(1)')).toBeNull()
    expect(safeAuthorizationUrl('http://gitlab.com/oauth')).toBeNull()
    expect(safeAuthorizationUrl('not a url')).toBeNull()
  })
})
