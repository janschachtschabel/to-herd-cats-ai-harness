import { createContext, useContext } from 'react'
import type { Me, Space, TreeNode } from '@/lib/api'
import type { WikiAbilities } from './abilities'

/** What every screen of a space's wiki shares: the space, what one may do there, the
 *  person, and the flat page list of the tree (for breadcrumbs, links, pickers). */
export interface Wiki {
  space: Space
  me: Me | null
  abilities: WikiAbilities
  nodes: TreeNode[]
  /** Lower-case page title → path, for `[[wiki links]]`. */
  titles: Map<string, string>
  /** Opens the new-page dialog (optionally with a title and a parent). */
  createPage: (initial?: { title?: string; parentId?: string | null }) => void
  /** The tag the tree is filtered by, if any. */
  tagFilter: string | null
  filterByTag: (tagId: string | null) => void
  /** Whether the tree shows only the pages whose review is due. */
  reviewFilter: boolean
  filterByReview: (on: boolean) => void
}

export const WikiContext = createContext<Wiki | null>(null)

export function useWiki(): Wiki {
  const wiki = useContext(WikiContext)
  if (!wiki) throw new Error('useWiki outside of a space wiki')
  return wiki
}

export function titleLookup(nodes: readonly TreeNode[]): Map<string, string> {
  return new Map(nodes.map((n) => [n.title.trim().toLowerCase(), n.path]))
}
