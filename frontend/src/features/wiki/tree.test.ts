import { describe, expect, test } from 'vitest'
import type { TreeNode } from '@/lib/api'
import { ancestorsOf, buildTree, isMemory, moveTargets, siblingsOf } from './tree'

function node(id: string, parent: string | null, sort: number, title = id, path = id): TreeNode {
  return {
    id,
    parent_id: parent,
    title,
    slug: path.split('/').at(-1)!,
    path,
    sort_order: sort,
    status: 'published',
    tags: [],
    review_due: false,
  }
}

describe("the agents' memory", () => {
  test('its top-level folder comes last, whatever its sort order', () => {
    const tree = buildTree([
      node('m', null, -5, 'Agenten', '_agenten'),
      node('h', 'm', 0, 'Hilda', '_agenten/hilda'),
      node('b', null, 2, 'B'),
      node('a', null, 1, 'A'),
    ])
    expect(tree.map((n) => n.id)).toEqual(['a', 'b', 'm'])
    expect(tree[2]!.children.map((n) => n.id)).toEqual(['h'])
  })

  test('is the folder `_agenten` at the top and what lies below it', () => {
    expect(isMemory({ path: '_agenten' })).toBe(true)
    expect(isMemory({ path: '_agenten/hilda/gedaechtnis' })).toBe(true)
    expect(isMemory({ path: 'agenten' })).toBe(false)
    expect(isMemory({ path: '_agenten-alt' })).toBe(false)
    expect(isMemory({ path: 'handbuch/_agenten' })).toBe(false)
  })
})

describe('buildTree', () => {
  test('nests children under their parents, siblings by sort order', () => {
    const flat = [
      node('b', null, 2),
      node('a', null, 1),
      node('a2', 'a', 2),
      node('a1', 'a', 1),
      node('a1x', 'a1', 0),
    ]
    const tree = buildTree(flat)
    expect(tree.map((n) => n.id)).toEqual(['a', 'b'])
    expect(tree[0]!.children.map((n) => n.id)).toEqual(['a1', 'a2'])
    expect(tree[0]!.children[0]!.children.map((n) => n.id)).toEqual(['a1x'])
    expect(tree[1]!.children).toEqual([])
  })

  test('a page whose parent is not in the list shows at the top', () => {
    const tree = buildTree([node('x', 'missing', 0), node('a', null, 1)])
    expect(tree.map((n) => n.id)).toEqual(['x', 'a'])
  })

  test('equal sort orders fall back to the title', () => {
    const tree = buildTree([node('2', null, 0, 'Zebra'), node('1', null, 0, 'Apfel')])
    expect(tree.map((n) => n.title)).toEqual(['Apfel', 'Zebra'])
  })
})

describe('tree helpers', () => {
  const flat = [node('a', null, 0), node('a1', 'a', 0), node('a1x', 'a1', 0), node('b', null, 1)]

  test('ancestors from the top down, without the page itself', () => {
    expect(ancestorsOf(flat, 'a1x').map((n) => n.id)).toEqual(['a', 'a1'])
    expect(ancestorsOf(flat, 'a')).toEqual([])
  })

  test('a page cannot move below itself or its descendants', () => {
    expect(moveTargets(flat, 'a1').map((n) => n.node.id)).toEqual(['a', 'b'])
    expect(moveTargets(flat, 'b').map((t) => [t.node.id, t.depth])).toEqual([
      ['a', 0],
      ['a1', 1],
      ['a1x', 2],
    ])
  })

  test('siblings under a parent, in order, without the moving page', () => {
    expect(siblingsOf(flat, null, 'b').map((n) => n.id)).toEqual(['a'])
    expect(siblingsOf(flat, 'a', 'x').map((n) => n.id)).toEqual(['a1'])
  })
})
