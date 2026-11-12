// Writes openapi.json (the backend's public API, without test-only routes) and
// src/lib/api-types.ts (its TypeScript types). No running server is needed: the
// schema comes from the FastAPI app object.
//
//   node scripts/generate-api.mjs           regenerate both files
//   node scripts/generate-api.mjs --check   exit 1 if the checked-in files are stale
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import openapiTS, { astToString } from 'openapi-typescript'

const root = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(root, '../backend')
const specFile = path.join(root, 'openapi.json')
const typesFile = path.join(root, 'src/lib/api-types.ts')

const DUMP = [
  'import json',
  'from app.web.public import create_public_app',
  'print(json.dumps(create_public_app().openapi(), indent=2, sort_keys=True))',
].join('; ')

function dumpSpec() {
  // HERD_ENVIRONMENT=production: the test routes are mounted only in "test".
  return execFileSync('uv', ['run', '--quiet', 'python', '-c', DUMP], {
    cwd: backend,
    env: { ...process.env, HERD_ENVIRONMENT: 'production', HERD_LOG_LEVEL: 'WARNING' },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  })
}

async function toTypes(spec) {
  const ast = await openapiTS(JSON.parse(spec), { defaultNonNullable: false })
  return astToString(ast)
}

const spec = dumpSpec()
const types = await toTypes(spec)

if (process.argv.includes('--check')) {
  const stale = [
    [specFile, spec],
    [typesFile, types],
  ].filter(([file, fresh]) => !fs.existsSync(file) || fs.readFileSync(file, 'utf8') !== fresh)
  if (stale.length > 0) {
    for (const [file] of stale) console.error(`stale: ${path.relative(root, file)}`)
    console.error('Run `npm run generate:api` and commit the result.')
    process.exit(1)
  }
  console.log('openapi.json and src/lib/api-types.ts are current.')
} else {
  fs.writeFileSync(specFile, spec)
  fs.writeFileSync(typesFile, types)
  console.log('Wrote openapi.json and src/lib/api-types.ts.')
}
