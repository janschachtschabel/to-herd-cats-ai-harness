import { Link } from '@tanstack/react-router'
import { FilePlus } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/features/shared/states'
import { buildTree } from './tree'
import { useWiki } from './WikiContext'

/** The space's start: its top-level pages, or how to begin. */
export function WikiHome() {
  const { t } = useTranslation()
  const { space, nodes, abilities, createPage } = useWiki()
  const top = useMemo(() => buildTree(nodes), [nodes])
  if (top.length === 0) {
    return (
      <EmptyState text={abilities.create ? t('wiki.home.emptyCreate') : t('wiki.home.empty')}>
        {abilities.create && (
          <Button onClick={() => createPage()}>
            <FilePlus aria-hidden />
            {t('wiki.home.createFirst')}
          </Button>
        )}
      </EmptyState>
    )
  }
  return (
    <section aria-labelledby="wiki-home-heading">
      <h2 id="wiki-home-heading" className="mb-3 text-base font-semibold">
        {t('wiki.home.title')}
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {top.map((node) => (
          <li key={node.id}>
            <Link
              to="/spaces/$spaceId/p/$"
              params={{ spaceId: space.id, _splat: node.path }}
              className="block rounded-lg border p-4 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="font-medium">{node.title}</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {node.status === 'draft'
                  ? t('wiki.page.draft')
                  : t('wiki.home.children', { count: node.children.length })}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
