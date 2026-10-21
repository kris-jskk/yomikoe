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
import { pauseAfterMs } from '../../src/player/pauses'

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
  /** MATH-5: maths ranges, offsets into `text`. */
  math?: { start: number; end: number; display: boolean }[]
}

export type DocumentSummary = {
  id: number
  status: string
  title?: string
  page_count?: number | null
  progress?: number
  position?: { segment_id: number | null; offset_ms: number } | null
  sections: { id: number; title: string; level: number; first_segment_id: number }[]
  settings: { voice_id: string | null; speed: number | null } | null
}

/**
 * FakeBackend timing rule (api/yomikoe/synthesis/fake.py): every `\S+` word of a segment's
 * normalized_text is round(24000 * 80 ms / speed) frames of silence at 24 kHz, words back to back.
 * SYN-8 (spec Q7, D53): each clip is followed by the pause of its block type (src/player/pauses.ts)
 * before the next one starts. Shared by play.spec.ts and soak.spec.ts.
 */
export const SAMPLE_RATE = 24_000
export const wordSec = (speed: number) =>
  Math.round((SAMPLE_RATE * 80) / 1000 / speed) / SAMPLE_RATE
export const wordCount = (s: Segment) => s.normalized_text.match(/\S+/g)?.length ?? 0

/** Global word index (reading order, from order 0) -> (segment, word index); null past end. */
export function wordAt(segs: Segment[], globalWord: number): { seg: Segment; word: number } | null {
  let left = globalWord
  for (const seg of segs) {
    const n = wordCount(seg)
    if (left < n) return { seg, word: left }
    left -= n
  }
  return null
}

/**
 * Global word index heard `t` seconds after the first clip's start, counting each segment's
 * SYN-8 pause after it; during a pause the highlight stays on that segment's last word.
 */
export function wordAtTime(segs: Segment[], t: number, ws: number): number {
  let left = t
  let before = 0
  for (const seg of segs) {
    const n = wordCount(seg)
    const dur = n * ws
    if (left < dur) return before + Math.floor(left / ws)
    left -= dur
    before += n
    const pause = pauseAfterMs(seg.type) / 1000
    if (left < pause) return Math.max(0, before - 1)
    left -= pause
  }
  return before
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

export function listDocuments(apiBase: string): Promise<DocumentSummary[]> {
  return getJson(`${apiBase}/documents`)
}

async function sendJson(method: string, url: string, body: unknown): Promise<void> {
  const r = await fetch(url, {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${method} ${url} -> ${r.status}: ${await r.text()}`)
}

/** Server defaults (api/tests/test_lib_gate.py, test_play11_settings.py): no voice, speed 1.25, factor 0.8. */
export const DEFAULT_GLOBAL_SETTINGS = {
  default_voice_id: null,
  default_speed: 1.25,
  equation_speed_factor: 0.8,
}

/**
 * Put the shared document and the global defaults back to a never-opened state (no position,
 * no per-document settings), so specs that save position or settings do not leak into others.
 */
export async function resetState(api: Api): Promise<void> {
  await sendJson('PATCH', `${api.apiBase}/documents/${api.documentId}`, {
    position: null,
    settings: { voice_id: null, speed: null },
  })
  await sendJson('PUT', `${api.apiBase}/settings`, DEFAULT_GLOBAL_SETTINGS)
}

/** Upload a fixture PDF from api/tests/fixtures/pdfs and wait until it is ready. */
export function uploadPdf(apiBase: string, name: string): Promise<Api> {
  return uploadPdfFile(apiBase, path.join(API_DIR, 'tests/fixtures/pdfs', name))
}

/** Upload a PDF from any absolute path and wait until it is ready (default 60 s). */
export async function uploadPdfFile(
  apiBase: string,
  pdf: string,
  timeoutMs = 60_000,
): Promise<Api> {
  const name = path.basename(pdf)
  const form = new FormData()
  form.append('file', new Blob([fs.readFileSync(pdf)], { type: 'application/pdf' }), name)
  const up = await fetch(`${apiBase}/documents`, { method: 'POST', body: form })
  if (up.status !== 202 && up.status !== 200) throw new Error(`upload ${name} -> ${up.status}`)
  const { id } = (await up.json()) as { id: number }
  const t1 = Date.now()
  for (;;) {
    const doc = await getDocument({ apiBase, documentId: id })
    if (doc.status === 'ready') return { apiBase, documentId: id }
    if (doc.status === 'failed') throw new Error(`document ${id} (${name}) failed`)
    if (Date.now() - t1 > timeoutMs)
      throw new Error(`document ${id} (${name}) not ready after ${timeoutMs} ms`)
    await sleep(250)
  }
}

/** DELETE a document (and its cached audio) so it does not leak into other specs. */
export async function deleteDocument(api: Api): Promise<void> {
  const r = await fetch(`${api.apiBase}/documents/${api.documentId}`, { method: 'DELETE' })
  if (!r.ok && r.status !== 404) throw new Error(`DELETE document ${api.documentId} -> ${r.status}`)
}

/** Absolute path of the repo's api/ directory (for the venv Python and generators). */
export const API_ROOT = API_DIR

/** Every PATCH /documents/{id} body the page sends, in order. */
export type PatchLog = { documentId: number; body: Record<string, unknown>; at: number }[]

export const test = base.extend<{ audioRequests: RequestLog; patches: PatchLog }, { api: Api }>({
  api: [
    // eslint-disable-next-line no-empty-pattern
    async ({}, provide) => {
      const port = process.env.YOMIKOE_E2E_API_PORT
      if (!port) throw new Error('YOMIKOE_E2E_API_PORT unset (set by playwright.config.ts)')
      const apiBase = `http://127.0.0.1:${port}`
      const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hn-e2e-'))
      const logPath = path.join(dataDir, 'api.log')
      const log = fs.openSync(logPath, 'a')
      const proc = spawn(
        path.join(API_DIR, '.venv/bin/python'),
        ['-m', 'yomikoe', 'serve', '--data-dir', dataDir, '--host', '127.0.0.1', '--port', port],
        {
          cwd: API_DIR,
          env: { ...process.env, YOMIKOE_TTS_BACKEND: 'fake' },
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
  patches: async ({ page }, provide) => {
    const log: PatchLog = []
    page.on('request', (req) => {
      const m = /^\/documents\/(\d+)$/.exec(new URL(req.url()).pathname)
      if (req.method() !== 'PATCH' || !m) return
      let body: Record<string, unknown> = {}
      try {
        body = (req.postDataJSON() as Record<string, unknown>) ?? {}
      } catch {
        /* keepalive beacons may carry no JSON body */
      }
      log.push({ documentId: Number(m[1]), body, at: Date.now() })
    })
    await provide(log)
  },
})

export { expect } from '@playwright/test'
