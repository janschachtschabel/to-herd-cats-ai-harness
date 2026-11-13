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
      notice={{ kind: 'markdown', block: 1, through: 2, detail: null }}
      doc={docOf('Eins', 'Zwei', 'Drei')}
    />,
  )
  expect(screen.getByText(/Blöcke 2 und 3/)).toHaveTextContent('„Zwei“')
})

test('one block is named with its start', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 0, through: null, detail: null }}
      doc={docOf('Eins', 'Zwei')}
    />,
  )
  expect(screen.getByText(/Block 1/)).toHaveTextContent('„Eins“')
})

test('tables over the cell cap are named too large, with the cap (review M2 U2)', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'tooLarge', block: 0, through: null, detail: null }}
      doc={docOf('Inventar')}
    />,
  )
  expect(screen.getByText(/zu groß/)).toHaveTextContent('10.000 Tabellenzellen')
})

test('the example fits the cause, and none is given when it is not known (U12)', () => {
  const { unmount } = render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 0, through: null, detail: 'address' }}
      doc={docOf('anna@firma.de+bernd@firma.de')}
    />,
  )
  expect(screen.getByText(/E-Mail-Adressen/)).toBeInTheDocument()
  expect(screen.queryByText(/Backslash/)).not.toBeInTheDocument()
  unmount()
  render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 0, through: null, detail: null }}
      doc={docOf('Text')}
    />,
  )
  expect(screen.getByText(/anders gelesen/)).toBeInTheDocument()
  expect(screen.queryByText(/etwa/)).not.toBeInTheDocument()
})

test('code with a backslash in a table cell is the example only for that cause', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'markdown', block: 0, through: null, detail: 'tableCode' }}
      doc={docOf('a|b')}
    />,
  )
  expect(screen.getByText(/Backslash direkt vor \|/)).toBeInTheDocument()
})

test('a check that took too long is named as the cause (review M4-1 P13)', () => {
  render(
    <UnsaveableNotice
      notice={{ kind: 'timeout', block: null, through: null, detail: null }}
      doc={docOf('Text')}
    />,
  )
  expect(screen.getByText(/zu lange gedauert/)).toHaveTextContent('Markdown-Editor')
})
