// Ported-from: to-herd-cats-ai@46352bb:frontend/src/features/wiki/PageTree.tsx
import { Link, useParams } from '@tanstack/react-router'
import { Bot, ChevronRight, ClipboardCheck, FilePen } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { TreeNode } from '@/lib/api'
import { cn } from '@/lib/utils'
import { buildTree, isMemory, type TreeItem } from './tree'

const ITEM = '[role="treeitem"]'

/** The space's pages as an ARIA tree: Up/Down move, Right/Left open/close or step
 *  in/out, Home/End jump, Enter opens the page. One item is in the tab order. */
export function PageTree({
  spaceId,
  nodes,
  label,
}: {
  spaceId: string
  nodes: TreeNode[]
  /** The tree's accessible name (default: "Seiten"). */
  label?: string
}) {
  const { t } = useTranslation()
  const tree = useMemo(() => buildTree(nodes), [nodes])
  const activePath = useParams({ strict: false, select: (p) => p._splat ?? null })
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())

  const toggle = (id: string, open?: boolean) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (open ?? next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  function onKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const current = (event.target as HTMLElement).closest<HTMLElement>(ITEM)
    if (!current) return
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(ITEM))
    const index = items.indexOf(current)
    const id = current.dataset.pageId!
    const expandable = current.getAttribute('aria-expanded') !== null
    const expanded = current.getAttribute('aria-expanded') === 'true'
    const focus = (el: HTMLElement | null | undefined) => {
      if (!el) return
      items.forEach((item) => item.setAttribute('tabindex', '-1'))
      el.setAttribute('tabindex', '0')
      el.focus()
    }
    switch (event.key) {
      case 'ArrowDown':
        focus(items[index + 1])
        break
      case 'ArrowUp':
        focus(items[index - 1])
        break
      case 'ArrowRight':
        if (expandable && !expanded) toggle(id, true)
        else if (expanded) focus(items[index + 1])
        break
      case 'ArrowLeft':
        if (expanded) toggle(id, false)
        else focus(current.parentElement?.closest<HTMLElement>(ITEM))
        break
      case 'Home':
        focus(items[0])
        break
      case 'End':
        focus(items[items.length - 1])
        break
      case 'Enter':
        current.querySelector<HTMLAnchorElement>('a')?.click()
        break
      default:
        return
    }
    event.preventDefault()
  }

  const activeIndex = Math.max(
    0,
    tree.findIndex((n) => n.path === activePath),
  )
  return (
    <ul
      role="tree"
      aria-label={label ?? t('wiki.tree.title')}
      className="flex flex-col gap-0.5"
      onKeyDown={onKeyDown}
    >
      {tree.map((node, i) => (
        <Item
          key={node.id}
          node={node}
          spaceId={spaceId}
          activePath={activePath}
          collapsed={collapsed}
          toggle={toggle}
          depth={0}
          tabbable={i === activeIndex}
        />
      ))}
    </ul>
  )
}

interface ItemProps {
  node: TreeItem
  spaceId: string
  activePath: string | null
  collapsed: Set<string>
  toggle: (id: string, open?: boolean) => void
  depth: number
  tabbable: boolean
}

function Item({ node, spaceId, activePath, collapsed, toggle, depth, tabbable }: ItemProps) {
  const { t } = useTranslation()
  const hasChildren = node.children.length > 0
  const expanded = hasChildren && !collapsed.has(node.id)
  const active = node.path === activePath
  const labelId = `page-tree-${node.id}`
  return (
    <li
      role="treeitem"
      data-page-id={node.id}
      aria-labelledby={labelId}
      aria-current={active ? 'page' : undefined}
      aria-expanded={hasChildren ? expanded : undefined}
      aria-level={depth + 1}
      tabIndex={tabbable ? 0 : -1}
      className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div
        className={cn(
          'flex items-center gap-1 rounded-md pr-2 text-sm',
          active ? 'bg-accent font-medium' : 'hover:bg-accent/60',
        )}
        style={{ paddingInlineStart: `${depth * 12}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            tabIndex={-1}
            aria-label={expanded ? t('wiki.tree.collapse') : t('wiki.tree.expand')}
            onClick={() => toggle(node.id)}
            className="flex size-6 shrink-0 items-center justify-center rounded hover:bg-accent"
          >
            <ChevronRight
              aria-hidden
              className={cn(
                'size-4 transition-transform motion-reduce:transition-none',
                expanded && 'rotate-90',
              )}
            />
          </button>
        ) : (
          <span className="size-6 shrink-0" aria-hidden />
        )}
        <Link
          to="/spaces/$spaceId/p/$"
          params={{ spaceId, _splat: node.path }}
          tabIndex={-1}
          className="flex min-w-0 flex-1 items-center gap-1.5 py-1"
        >
          <span id={labelId} className="truncate">
            {node.title}
          </span>
          {isMemory(node) && (
            <Bot
              role="img"
              aria-label={t('wiki.memory.mark')}
              className="size-3.5 shrink-0 text-violet-700 dark:text-violet-300"
            />
          )}
          {node.review_due && (
            <ClipboardCheck
              role="img"
              aria-label={t('wiki.review.due')}
              className="size-3.5 shrink-0 text-amber-700 dark:text-amber-300"
            />
          )}
          {node.status === 'draft' && (
            <FilePen
              role="img"
              aria-label={t('wiki.page.draft')}
              className="size-3.5 shrink-0 text-muted-foreground"
            />
          )}
        </Link>
      </div>
      {expanded && (
        <ul role="group" className="flex flex-col gap-0.5">
          {node.children.map((child) => (
            <Item
              key={child.id}
              node={child}
              spaceId={spaceId}
              activePath={activePath}
              collapsed={collapsed}
              toggle={toggle}
              depth={depth + 1}
              tabbable={false}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
