import { expect, test } from 'vitest'
import * as Y from 'yjs'
import { blockStart, unsaveable } from './unsaveable'

test('the notice of the collab process names the kind of cause and the block', () => {
  expect(unsaveable('herd:unrepresentable:markdown:3')).toEqual({ kind: 'markdown', block: 3 })
  expect(unsaveable('herd:unrepresentable:structure:')).toEqual({ kind: 'structure', block: null })
  expect(unsaveable('herd:unrepresentable')).toEqual({ kind: 'unknown', block: null })
  expect(unsaveable('herd:unrepresentable:neu:x')).toEqual({ kind: 'unknown', block: null })
  expect(unsaveable('herd:representable')).toBeNull()
})

test('a block is named by the start of its text', () => {
  const doc = new Y.Doc()
  const fragment = doc.getXmlFragment('default')
  const paragraph = new Y.XmlElement('paragraph')
  paragraph.insert(0, [new Y.XmlText('Erster Absatz')])
  const table = new Y.XmlElement('table')
  const row = new Y.XmlElement('tableRow')
  const cell = new Y.XmlElement('tableHeader')
  const line = new Y.XmlElement('tableParagraph')
  const code = new Y.XmlText()
  code.insert(0, 'a\\| und dann noch ein sehr langer Text in der Zelle', { code: true })
  line.insert(0, [code])
  cell.insert(0, [line])
  row.insert(0, [cell])
  table.insert(0, [row])
  fragment.insert(0, [paragraph, table])
  expect(blockStart(doc, 0)).toBe('Erster Absatz')
  expect(blockStart(doc, 1)).toBe('a\\| und dann noch ein sehr langer Text …')
  expect(blockStart(doc, 5)).toBe('')
})
