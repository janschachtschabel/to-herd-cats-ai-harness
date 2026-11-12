// Checks the translations (run: node scripts/check-i18n.mjs, exit 1 on a finding):
// - de and en have the same keys, the same {{placeholders}} per key, and the plural
//   forms each language needs (i18next suffixes such as _one/_other);
// - every literal key passed to t() exists; a template key such as `roles.${role}` must
//   name an existing group of keys;
// - no user-facing text is written into TSX directly: JSX text and the attributes
//   aria-label, title, placeholder and alt must come from t().
import fs from 'node:fs'
import path from 'node:path'
import { createInstance } from 'i18next'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const LOCALES = ['de', 'en']
const TEXT_ATTRIBUTES = new Set(['aria-label', 'title', 'placeholder', 'alt'])
// Text that is the same in every language.
const NATIVE = new Set(['–', '·', '(', ')'])

const problems = []

function load(locale) {
  return JSON.parse(fs.readFileSync(path.join(root, `src/locales/${locale}/common.json`), 'utf8'))
}

function flatten(tree, prefix = '', out = {}) {
  for (const [key, value] of Object.entries(tree)) {
    const full = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object') flatten(value, full, out)
    else out[full] = String(value)
  }
  return out
}

const PLURAL = /_(zero|one|two|few|many|other)$/
const placeholders = (text) =>
  [...text.matchAll(/{{\s*(\w+)\s*}}/g)]
    .map((m) => m[1])
    .sort()
    .join(',')

const resources = Object.fromEntries(LOCALES.map((l) => [l, load(l)]))
const flat = Object.fromEntries(LOCALES.map((l) => [l, flatten(resources[l])]))

// Same keys (plural forms compared per base key below).
const base = (key) => key.replace(PLURAL, '')
const bases = Object.fromEntries(LOCALES.map((l) => [l, new Set(Object.keys(flat[l]).map(base))]))
for (const [a, b] of [
  ['de', 'en'],
  ['en', 'de'],
]) {
  for (const key of bases[a]) if (!bases[b].has(key)) problems.push(`${b}: missing key ${key}`)
}

// Plural forms each language needs, and placeholders.
for (const locale of LOCALES) {
  const needed = new Intl.PluralRules(locale).resolvedOptions().pluralCategories
  const forms = {}
  for (const key of Object.keys(flat[locale])) {
    const match = key.match(PLURAL)
    if (match) (forms[base(key)] ??= new Set()).add(match[1])
  }
  for (const [key, have] of Object.entries(forms)) {
    for (const category of needed) {
      if (!have.has(category)) problems.push(`${locale}: ${key} lacks plural form _${category}`)
    }
  }
}
for (const key of Object.keys(flat.de)) {
  if (key in flat.en && placeholders(flat.de[key]) !== placeholders(flat.en[key])) {
    problems.push(`placeholders differ: ${key}`)
  }
}

// Plurals resolve as i18next resolves them.
for (const locale of LOCALES) {
  const i18n = createInstance()
  await i18n.init({
    lng: locale,
    resources: { [locale]: { common: resources[locale] } },
    defaultNS: 'common',
    initAsync: false,
  })
  const one = i18n.t('validation.tooShort', { count: 1 })
  const many = i18n.t('validation.tooShort', { count: 10 })
  if (one === 'validation.tooShort' || !one.includes('1') || !many.includes('10')) {
    problems.push(`${locale}: plural validation.tooShort does not resolve`)
  }
}

// Keys used in the code, and text written into TSX.
const known = new Set(Object.keys(flat.de).map(base))
const isKnownPrefix = (prefix) => [...known].some((key) => key.startsWith(prefix))

function sourceFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'test' ? [] : sourceFiles(file)
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [file] : []
  })
}

for (const file of sourceFiles(path.join(root, 'src'))) {
  if (file.endsWith('api-types.ts')) continue
  const rel = path.relative(root, file)
  const source = fs.readFileSync(file, 'utf8')
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const at = (node) => `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`

  function checkKey(arg) {
    if (ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)) {
      if (!known.has(arg.text)) problems.push(`${at(arg)}: unknown key ${arg.text}`)
    } else if (ts.isTemplateExpression(arg)) {
      if (!isKnownPrefix(arg.head.text)) problems.push(`${at(arg)}: unknown keys ${arg.head.text}…`)
    } else if (ts.isConditionalExpression(arg)) {
      checkKey(arg.whenTrue)
      checkKey(arg.whenFalse)
    }
  }

  function visit(node) {
    if (ts.isCallExpression(node) && node.arguments[0]) {
      const callee = node.expression.getText(sf)
      if (callee === 't' || callee === 'i18n.t') checkKey(node.arguments[0])
    }
    if (ts.isJsxText(node)) {
      const text = node.getText(sf).replace(/\s+/g, ' ').trim()
      if (/\p{L}/u.test(text) && !NATIVE.has(text)) problems.push(`${at(node)}: raw text "${text}"`)
    }
    if (
      ts.isJsxAttribute(node) &&
      TEXT_ATTRIBUTES.has(node.name.getText(sf)) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer) &&
      /\p{L}/u.test(node.initializer.text)
    ) {
      problems.push(`${at(node)}: raw ${node.name.getText(sf)} "${node.initializer.text}"`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
}

if (problems.length > 0) {
  console.error(problems.join('\n'))
  process.exitCode = 1
} else {
  console.log(
    `de/en: ${Object.keys(flat.de).length} entries; keys, placeholders and plurals match; ` +
      'every t() key exists; no raw text in TSX.',
  )
}
