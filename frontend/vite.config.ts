/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend's public port (HERD_PUBLIC_PORT); override with HERD_API_PROXY.
const apiTarget = process.env.HERD_API_PROXY ?? 'http://localhost:8080'

// The live editor imports the collab process's schema (`../collab/schema.mjs`), so the
// browser builds exactly the documents the server turns into Markdown. Its packages
// resolve from this project (one copy of Tiptap and Yjs, whatever collab/ has installed).
const collabDir = path.resolve(import.meta.dirname, '../collab')
const SHARED = [
  '@tiptap/core',
  '@tiptap/pm',
  '@tiptap/starter-kit',
  '@tiptap/extension-code-block',
  '@tiptap/extension-image',
  '@tiptap/extension-table',
  '@tiptap/extension-list',
  '@tiptap/extension-link',
  '@tiptap/extension-paragraph',
  'yjs',
]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
      '@collab': collabDir,
    },
    dedupe: SHARED,
  },
  server: {
    port: 5173,
    fs: { allow: ['.', collabDir] },
    proxy: { '/api': { target: apiTarget }, '/collab': { target: apiTarget, ws: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
