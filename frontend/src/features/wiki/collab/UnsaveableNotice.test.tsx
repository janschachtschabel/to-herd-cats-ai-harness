import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import * as Y from 'yjs'
import { UnsaveableNotice } from './UnsaveableNotice'

function docOf(...texts: string[]) {
  const doc = new Y.Doc()
  doc.getXmlFragment('default').insert(
    0,
    texts.map((text) => {
      const paragraph = new Y.XmlElement('paragraph')
      paragraph.insert(0, [new Y.XmlText(text)])
      return paragraph
    }),
  )
  return doc
}

test('two neighbours that fail only together are both named (review M2 U1)', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 1, through: 2 }}
      doc={docOf('Eins', 'Zwei', 'Drei')}
    />,
  )
  expect(screen.getByText(/Blöcke 2 und 3/)).toHaveTextContent('„Zwei“')
})

test('one block is named with its start', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 0, through: null }}
      doc={docOf('Eins', 'Zwei')}
    />,
  )
  expect(screen.getByText(/Block 1/)).toHaveTextContent('„Eins“')
})

test('tables over the cell cap are named too large, with the cap (review M2 U2)', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'tooLarge', block: 0, through: null }}
      doc={docOf('Inventar')}
    />,
  )
  expect(screen.getByText(/zu groß/)).toHaveTextContent('10.000 Tabellenzellen')
})
