/**
 * E2E harness (spec §8): a worker-scoped fixture starts the API with FakeBackend on the port
 * chosen in playwright.config.ts and a temp data dir, uploads FIXTURE_PDF, waits for ready,
 * exposes {apiBase, documentId}, and stops the API by its PID at worker teardown.
 */
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test as base } from '@playwright/test'

/** Smallest fixture PDF (bytes) with at least 30 body segments: 111 body / 198 total. */
export const FIXTURE_PDF = 'academic_01_seahelm_audio.pdf'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const API_DIR = path.join(REPO, 'api')

export type Api = { apiBase: string; documentId: number }

export type Segment = {
  id: number
  order: number
  type: string
  section_id: number | null
  text: string
  normalized_text: string
}

export type DocumentSummary = {
  id: number
  status: string
  sections: { id: number; title: string; level: number; first_segment_id: number }[]
  settings: { voice_id: string | null; speed: number | null } | null
}

export type RequestLog = { url: string; at: number }[]

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`)
  return (await r.json()) as T
}

export async function getSegments(api: Api): Promise<Segment[]> {
  const out: Segment[] = []
  let from: number | null = 0
  while (from !== null) {
    const page: { segments: Segment[]; next_from: number | null } = await getJson(
      `${api.apiBase}/documents/${api.documentId}/segments?from=${from}&limit=500`,
    )
    out.push(...page.segments)
    from = page.next_from
  }
  return out.sort((a, b) => a.order - b.order)
}

export function getDocument(api: Api): Promise<DocumentSummary> {
  return getJson(`${api.apiBase}/documents/${api.documentId}`)
}

export const test = base.extend<{ audioRequests: RequestLog }, { api: Api }>({
  api: [
    // eslint-disable-next-line no-empty-pattern
    async ({}, provide) => {
      const port = process.env.HEARNARRO_E2E_API_PORT
      if (!port) throw new Error('HEARNARRO_E2E_API_PORT unset (set by playwright.config.ts)')
      const apiBase = `http://127.0.0.1:${port}`
      const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hn-e2e-'))
      const logPath = path.join(dataDir, 'api.log')
      const log = fs.openSync(logPath, 'a')
      const proc = spawn(
        path.join(API_DIR, '.venv/bin/python'),
        ['-m', 'hearnarro', 'serve', '--data-dir', dataDir, '--host', '127.0.0.1', '--port', port],
        {
          cwd: API_DIR,
          env: { ...process.env, HEARNARRO_TTS_BACKEND: 'fake' },
          stdio: ['ignore', log, log],
        },
      )
      const pid = proc.pid
      if (pid === undefined) throw new Error('API process did not start')
      let exited = false
      proc.on('exit', () => (exited = true))
      const fail = (why: string) =>
        new Error(`${why}; API log ${logPath}:\n${fs.readFileSync(logPath, 'utf8').slice(-2000)}`)
      try {
        const t0 = Date.now()
        for (;;) {
          if (exited) throw fail('API exited during startup')
          if (Date.now() - t0 > 30_000) throw fail('API not listening after 30 s')
          try {
            if ((await fetch(`${apiBase}/documents`)).ok) break
          } catch {
            /* not listening yet */
          }
          await sleep(200)
        }
        const pdf = path.join(API_DIR, 'tests/fixtures/pdfs', FIXTURE_PDF)
        const form = new FormData()
        form.append(
          'file',
          new Blob([fs.readFileSync(pdf)], { type: 'application/pdf' }),
          FIXTURE_PDF,
        )
        const up = await fetch(`${apiBase}/documents`, { method: 'POST', body: form })
        if (up.status !== 202 && up.status !== 200) throw fail(`upload -> ${up.status}`)
        const { id } = (await up.json()) as { id: number }
        const t1 = Date.now()
        for (;;) {
          const doc = await getDocument({ apiBase, documentId: id })
          if (doc.status === 'ready') break
          if (doc.status === 'failed') throw fail(`document ${id} failed`)
          if (Date.now() - t1 > 60_000) throw fail(`document ${id} not ready after 60 s`)
          await sleep(250)
        }
        const segs = await getSegments({ apiBase, documentId: id })
        console.log(
          `[e2e-fixture] api pid ${pid} at ${apiBase}; ${FIXTURE_PDF} -> document ${id} ready ` +
            `after ${Date.now() - t1} ms, ${segs.length} segments`,
        )
        await provide({ apiBase, documentId: id })
      } finally {
        process.kill(pid, 'SIGTERM')
        for (let i = 0; i < 50 && !exited; i++) await sleep(100)
        if (!exited) process.kill(pid, 'SIGKILL')
        fs.closeSync(log)
        console.log(`[e2e-fixture] api pid ${pid} stopped (exited=${exited})`)
        fs.rmSync(dataDir, { recursive: true, force: true })
      }
    },
    { scope: 'worker', timeout: 120_000 },
  ],
  audioRequests: async ({ page }, provide) => {
    const log: RequestLog = []
    page.on('request', (req) => {
      if (new URL(req.url()).pathname.startsWith('/audio/'))
        log.push({ url: req.url(), at: Date.now() })
    })
    await provide(log)
  },
})

export { expect } from '@playwright/test'
