// The commands' types come from the extensions' packages (the schema module is plain JS).
import type {} from '@tiptap/extension-code-block'
import type {} from '@tiptap/extension-list'
import type {} from '@tiptap/starter-kit'
import { useEditorState, type Editor } from '@tiptap/react'
import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Heading3,
  Italic,
  List,
  ListChecks,
  ListOrdered,
  Minus,
  Unlink,
  Quote,
  SquareCode,
  Strikethrough,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { markInput } from '@collab/editor.mjs'
import { Button } from '@/components/ui/button'

type Chain = ReturnType<Editor['chain']>

const TOOLS = [
  {
    id: 'bold',
    icon: Bold,
    active: (e: Editor) => e.isActive('bold'),
    run: (c: Chain) => c.toggleBold(),
  },
  {
    id: 'italic',
    icon: Italic,
    active: (e: Editor) => e.isActive('italic'),
    run: (c: Chain) => c.toggleItalic(),
  },
  {
    id: 'strike',
    icon: Strikethrough,
    active: (e: Editor) => e.isActive('strike'),
    run: (c: Chain) => c.toggleStrike(),
  },
  {
    id: 'code',
    icon: Code,
    active: (e: Editor) => e.isActive('code'),
    run: (c: Chain) => c.toggleCode(),
  },
  {
    id: 'h1',
    icon: Heading1,
    active: (e: Editor) => e.isActive('heading', { level: 1 }),
    run: (c: Chain) => c.toggleHeading({ level: 1 }),
  },
  {
    id: 'h2',
    icon: Heading2,
    active: (e: Editor) => e.isActive('heading', { level: 2 }),
    run: (c: Chain) => c.toggleHeading({ level: 2 }),
  },
  {
    id: 'h3',
    icon: Heading3,
    active: (e: Editor) => e.isActive('heading', { level: 3 }),
    run: (c: Chain) => c.toggleHeading({ level: 3 }),
  },
  {
    id: 'bulletList',
    icon: List,
    active: (e: Editor) => e.isActive('bulletList'),
    run: (c: Chain) => c.toggleBulletList(),
  },
  {
    id: 'orderedList',
    icon: ListOrdered,
    active: (e: Editor) => e.isActive('orderedList'),
    run: (c: Chain) => c.toggleOrderedList(),
  },
  {
    id: 'taskList',
    icon: ListChecks,
    active: (e: Editor) => e.isActive('taskList'),
    run: (c: Chain) => c.toggleTaskList(),
  },
  {
    id: 'quote',
    icon: Quote,
    active: (e: Editor) => e.isActive('blockquote'),
    run: (c: Chain) => c.toggleBlockquote(),
  },
  {
    id: 'codeBlock',
    icon: SquareCode,
    active: (e: Editor) => e.isActive('codeBlock'),
    run: (c: Chain) => c.toggleCodeBlock(),
  },
  { id: 'rule', icon: Minus, active: null, run: (c: Chain) => c.setHorizontalRule() },
] as const

/** Takes the link at the caret (or in the selection) off, keeping its text (review M2
 *  U5: typing could link a word nobody meant as a link, and nothing took it off). */
const UNLINK = {
  id: 'unlink',
  icon: Unlink,
  enabled: (e: Editor) => e.isActive('link'),
  run: (c: Chain) => c.extendMarkRange('link').unsetLink(),
} as const

/** Formatting buttons; each says whether it applies at the cursor (aria-pressed). */
export function Toolbar({ editor, disabled }: { editor: Editor; disabled: boolean }) {
  const { t } = useTranslation()
  const active = useEditorState({
    editor,
    selector: ({ editor: current }) =>
      TOOLS.map((tool) => (tool.active ? tool.active(current) : false)),
  })
  const inLink = useEditorState({
    editor,
    selector: ({ editor: current }) => UNLINK.enabled(current),
  })
  return (
    <div
      role="toolbar"
      aria-label={t('wiki.live.toolbar')}
      className="flex flex-wrap gap-0.5 border-b p-1"
    >
      {TOOLS.map((tool, i) => (
        <Button
          key={tool.id}
          type="button"
          variant={active[i] ? 'secondary' : 'ghost'}
          size="icon-sm"
          disabled={disabled}
          aria-label={t(`wiki.live.tools.${tool.id}`)}
          aria-pressed={tool.active ? active[i] : undefined}
          onClick={() => {
            markInput(editor)
            tool.run(editor.chain().focus()).run()
          }}
        >
          <tool.icon aria-hidden />
        </Button>
      ))}
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        disabled={disabled || !inLink}
        aria-label={t('wiki.live.tools.unlink')}
        onClick={() => {
          markInput(editor)
          UNLINK.run(editor.chain().focus()).run()
        }}
      >
        <UNLINK.icon aria-hidden />
      </Button>
    </div>
  )
}
