import type { TreeNode } from '@/lib/api'

/** A page of the tree with its children, built from the server's flat list. */
export interface TreeItem extends TreeNode {
  children: TreeItem[]
}

function bySortOrder(a: TreeNode, b: TreeNode): number {
  return a.sort_order - b.sort_order || a.title.localeCompare(b.title)
}

/** The flat list (ordered by path) as a tree: children under their parents, siblings
 *  by `sort_order`. A page whose parent is not in the list is shown at the top. */
export function buildTree(nodes: readonly TreeNode[]): TreeItem[] {
  const items = new Map<string, TreeItem>(nodes.map((n) => [n.id, { ...n, children: [] }]))
  const roots: TreeItem[] = []
  for (const item of items.values()) {
    const parent = item.parent_id ? items.get(item.parent_id) : undefined
    if (parent) parent.children.push(item)
    else roots.push(item)
  }
  const sort = (list: TreeItem[]) => {
    list.sort(bySortOrder)
    list.forEach((item) => sort(item.children))
  }
  sort(roots)
  return roots
}

/** The pages above `id`, from the top down. */
export function ancestorsOf(nodes: readonly TreeNode[], id: string): TreeNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const chain: TreeNode[] = []
  let current = byId.get(id)?.parent_id
  while (current && chain.length < nodes.length) {
    const parent = byId.get(current)
    if (!parent) break
    chain.unshift(parent)
    current = parent.parent_id
  }
  return chain
}

/** Every page in tree order with its depth (for pickers). */
export function flattenTree(
  tree: readonly TreeItem[],
  depth = 0,
): { node: TreeItem; depth: number }[] {
  return tree.flatMap((node) => [{ node, depth }, ...flattenTree(node.children, depth + 1)])
}

/** Where `id` may move to: every page except itself and the pages below it. */
export function moveTargets(nodes: readonly TreeNode[], id: string) {
  const prune = (list: TreeItem[]): TreeItem[] =>
    list.filter((n) => n.id !== id).map((n) => ({ ...n, children: prune(n.children) }))
  return flattenTree(prune(buildTree(nodes)))
}

/** The pages under `parentId` (null: the top) in order, without `exceptId`. */
export function siblingsOf(
  nodes: readonly TreeNode[],
  parentId: string | null,
  exceptId: string,
): TreeNode[] {
  const known = new Set(nodes.map((n) => n.id))
  return nodes
    .filter((n) => n.id !== exceptId)
    .filter((n) =>
      parentId === null ? !n.parent_id || !known.has(n.parent_id) : n.parent_id === parentId,
    )
    .sort(bySortOrder)
}
