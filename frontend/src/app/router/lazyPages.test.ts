import { describe, expect, test } from 'vitest'

/** The router's own files, as text. */
const SOURCES = import.meta.glob<string>(['./*.tsx', '!./*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

/** Routes whose component wraps a lazy page (`<Page …/>` inside a function) and whose
 *  loader does not import it. The router waits only for what its loaders and its own
 *  component load: such a page is imported during the render instead, behind a bare
 *  fallback, after the router already said it is done. */
function unpreloadedPages(source: string): string[] {
  const lazy = [...source.matchAll(/const (\w+) = lazyRouteComponent/g)].map((m) => m[1]!)
  const missing: string[] = []
  for (const route of source.matchAll(/const (\w+) = createRoute\(\{([\s\S]*?)\n\}\)/g)) {
    const [, name, body] = route as unknown as [string, string, string]
    const loader = /loader:([\s\S]*?)\n {2}component:/.exec(body)?.[1] ?? ''
    for (const page of lazy) {
      if (new RegExp(`<${page}\\b`).test(body) && !loader.includes(`${page}.preload`)) {
        missing.push(`${name}: ${page}`)
      }
    }
  }
  return missing
}

describe('lazy pages', () => {
  test('a route that wraps a lazy page imports it in its loader', () => {
    expect(Object.keys(SOURCES)).toContain('./routes.tsx')
    expect(Object.values(SOURCES).flatMap(unpreloadedPages)).toEqual([])
  })
})
