import { expect, test } from 'vitest'
import * as Y from 'yjs'
import { blockStart, unsaveable } from './unsaveable'

test('the notice of the collab process names the kind of cause and the block', () => {
  const none = { through: null, detail: null }
  expect(unsaveable('herd:unrepresentable:markdown:3')).toEqual({
    kind: 'markdown',
    block: 3,
    ...none,
  })
  expect(unsaveable('herd:unrepresentable:structure:')).toEqual({
    kind: 'structure',
    block: null,
    ...none,
  })
  expect(unsaveable('herd:unrepresentable')).toEqual({ kind: 'unknown', block: null, ...none })
  expect(unsaveable('herd:unrepresentable:neu:x')).toEqual({
    kind: 'unknown',
    block: null,
    ...none,
  })
  // Two neighbours that fail only together (review M2 U1).
  expect(unsaveable('herd:unrepresentable:markdown:1-2')).toEqual({
    kind: 'markdown',
    block: 1,
    through: 2,
    detail: null,
  })
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

test('a state over the table cell cap is too large (review M2 U2)', () => {
  expect(unsaveable('herd:unrepresentable:tooLarge:4')).toEqual({
    kind: 'tooLarge',
    block: 4,
    through: null,
    detail: null,
  })
})

test('the kind of difference comes after the place (review M2 U12)', () => {
  expect(unsaveable('herd:unrepresentable:markdown:0:address')).toEqual({
    kind: 'markdown',
    block: 0,
    through: null,
    detail: 'address',
  })
  expect(unsaveable('herd:unrepresentable:markdown::neu')?.detail).toBeNull()
  expect(unsaveable('herd:unrepresentable:markdown:2')?.detail).toBeNull()
})
