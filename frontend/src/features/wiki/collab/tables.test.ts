import { Editor, type JSONContent } from '@tiptap/core'
import { afterEach, describe, expect, test } from 'vitest'
import { extensions } from '@collab/schema.mjs'
import { flattenTableSpans } from '@collab/tables.mjs'
import { jsonToMarkdown } from '@collab/serialize.mjs'

let editor: Editor | null = null
afterEach(() => {
  editor?.destroy()
  editor = null
})

const TABLE = '| a | b |\n| --- | --- |\n| 1 | 2 |'
const tableDoc: JSONContent = {
  type: 'doc',
  content: [
    {
      type: 'table',
      content: [
        ['tableHeader', 'a', 'b'],
        ['tableCell', '1', '2'],
      ].map(([type, ...cells]) => ({
        type: 'tableRow',
        content: cells.map((value) => ({
          type,
          content: [{ type: 'tableParagraph', content: [{ type: 'text', text: value }] }],
        })),
      })),
    },
  ],
}

/** The editor with the cursor in the cell holding `text`. */
function inCell(text: string) {
  editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
  editor.commands.setContent(tableDoc)
  let at = 0
  editor.state.doc.descendants((node, pos) => {
    if (node.isText && node.text === text) at = pos + 1
  })
  editor.commands.setTextSelection(at)
  return editor
}

function press(key: string, modifiers: KeyboardEventInit = {}) {
  editor!.view.dom.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...modifiers }),
  )
}

describe('tables in the live editor (review M2 T4, T8)', () => {
  for (const [cell, where] of [
    ['1', 'a body cell'],
    ['a', 'a header cell'],
  ]) {
    for (const [name, modifiers] of [
      ['Enter', {}],
      ['Shift+Enter', { shiftKey: true }],
      ['Mod+Enter', { ctrlKey: true }],
    ] as const) {
      test(`${name} in ${where} changes nothing`, () => {
        inCell(cell!)
        press('Enter', modifiers)
        expect(jsonToMarkdown(editor!.getJSON())).toBe(TABLE)
      })
    }
  }

  test('a pasted table with merged cells becomes plain cells, content in the first', () => {
    const root = document.createElement('div')
    root.innerHTML =
      '<table><tr><th colspan="2">Kopf</th><th>c</th></tr>' +
      '<tr><td rowspan="2">lang</td><td>x</td><td>y</td></tr>' +
      '<tr><td>z</td><td>w</td></tr></table>'
    const rows = [...flattenTableSpans(root).querySelectorAll('tr')].map((row) =>
      [...row.children].map((cell) => `${cell.tagName}:${cell.textContent}`),
    )
    expect(rows).toEqual([
      ['TH:Kopf', 'TH:', 'TH:c'],
      ['TD:lang', 'TD:x', 'TD:y'],
      ['TD:', 'TD:z', 'TD:w'],
    ])
    expect(root.querySelector('[colspan], [rowspan]')).toBeNull()
  })

  test('pasting a table with merged cells gives a table Markdown can say', () => {
    editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
    editor.view.pasteHTML(
      '<table><tr><th colspan="2">Kopf</th></tr><tr><td>x</td><td>y</td></tr></table>',
      new Event('paste') as ClipboardEvent, // jsdom has no ClipboardEvent
    )
    const json = JSON.stringify(editor.getJSON())
    expect(json).not.toMatch(/"(colspan|rowspan)":(?!1\b)/)
    expect(jsonToMarkdown(editor.getJSON())).toContain('| Kopf |  |\n| --- | --- |\n| x | y |')
  })

  test('HTML cannot merge cells', () => {
    editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
    editor.commands.setContent('<table><tr><td colspan="3" rowspan="2">x</td></tr></table>')
    const cells: Record<string, unknown>[] = []
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'tableCell' || node.type.name === 'tableHeader') cells.push(node.attrs)
    })
    expect(cells.every((attrs) => attrs.colspan === 1 && attrs.rowspan === 1)).toBe(true)
  })
})
