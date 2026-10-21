/**
 * M4 gate clause 2 (spec §0, §4 D29): browser soak on the generated 300-page PDF
 * (api/tests/soak_util.py). Asserted on Chromium (D22). Measures first render (first `.seg`
 * visible, last `.seg` attached), checks the highlighted word at three probe times (PLAY-2),
 * skips to the last section, and checks a reload restores the position within one sentence
 * (LIB-2). The numbers are printed as `[soak]` lines and decide D29.
 */
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import type { Page } from '@playwright/test'
import {
  API_ROOT,
  deleteDocument,
  expect,
  getDocument,
  getSegments,
  test,
  uploadPdfFile,
  type Api,
  type PatchLog,
  type Segment,
} from './fixtures'

test.skip(({ browserName }) => browserName !== 'chromium', 'gate clause 2 is asserted on Chromium')

// Same shape as play.spec.ts so the global declarations merge.
type Hn = {
  firstStartAt: number | null
  now: () => number
  entries: { segmentId: number; startAt: number; durationSec: number }[]
}
declare global {
  interface Window {
    __yomikoe?: Hn
  }
}

const FIRST_RENDER_LIMIT_MS = 5_000

// FakeBackend timing (api/yomikoe/synthesis/fake.py; same rule as play.spec.ts).
const SAMPLE_RATE = 24_000
const wordSec = (speed: number) => Math.round((SAMPLE_RATE * 80) / 1000 / speed) / SAMPLE_RATE
const wordCount = (s: Segment) => s.normalized_text.match(/\S+/g)?.length ?? 0

function wordAt(segs: Segment[], globalWord: number): { seg: Segment; word: number } | null {
  let left = globalWord
  for (const seg of segs) {
    const n = wordCount(seg)
    if (left < n) return { seg, word: left }
    left -= n
  }
  return null
}

function tokenIndexAt(text: string, c: number): number {
  const re = /\S+/g
  let i = 0
  for (let m = re.exec(text); m; m = re.exec(text), i++) {
    if (c < m.index + m[0].length) return i
  }
  return i - 1
}

async function tokenForWord(api: Api, seg: Segment, word: number, voice: string, speed: number) {
  const r = await fetch(`${api.apiBase}/audio/${seg.id}?voice=${voice}&speed=${speed.toFixed(2)}`)
  const ts = JSON.parse(r.headers.get('x-timestamps') ?? '[]') as { char_start: number }[]
  return tokenIndexAt(seg.text, ts[Math.min(word, ts.length - 1)].char_start)
}

const activeSeg = (page: Page) =>
  page.evaluate(() => {
    const h = window.__yomikoe
    const w = document.querySelector<HTMLElement>('.w.active')
    const seg = w?.closest<HTMLElement>('.seg')
    return {
      elapsed: h && h.firstStartAt != null ? h.now() - h.firstStartAt : null,
      order: seg ? Number(seg.dataset.order) : null,
      id: seg ? Number(seg.dataset.id) : null,
      i: w ? Number(w.dataset.i) : null,
    }
  })

/** In-page ms since navigation start when the first `.seg` is visible and the last attached. */
async function measureRender(page: Page, lastId: number) {
  const firstVisible = (await (
    await page.waitForFunction(
      () => {
        const el = document.querySelector('.seg[data-order]')
        if (!el) return null
        const r = el.getBoundingClientRect()
        return r.height > 0 && r.width > 0 ? performance.now() : null
      },
      undefined,
      { timeout: 60_000, polling: 'raf' },
    )
  ).jsonValue()) as number
  const lastAttached = (await (
    await page.waitForFunction(
      (id) => (document.querySelector(`.seg[data-id="${id}"]`) ? performance.now() : null),
      lastId,
      { timeout: 60_000, polling: 'raf' },
    )
  ).jsonValue()) as number
  const count = await page.locator('.seg[data-order]').count()
  return { firstVisible, lastAttached, count }
}

type Position = { segment_id: number; offset_ms: number }
const positionPatches = (log: PatchLog, id: number) =>
  log.filter((p) => p.documentId === id && p.body.position).map((p) => p.body.position as Position)

test('soak: 300-page document renders under 5 s, highlights at 3 probes, skips to the last section and restores on reload (M4 gate clause 2; PLAY-2, LIB-2, D29)', async ({
  page,
  api,
  patches,
  audioRequests,
}) => {
  test.setTimeout(180_000)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hn-soak-'))
  const pdf = path.join(dir, 'soak_300.pdf')
  let doc: Api | null = null
  try {
    const tg = Date.now()
    execFileSync(
      path.join(API_ROOT, '.venv/bin/python'),
      [
        '-c',
        'import sys; from pathlib import Path; sys.path.insert(0, "tests"); ' +
          'from soak_util import generate_soak_pdf; generate_soak_pdf(Path(sys.argv[1]), pages=300)',
        pdf,
      ],
      { cwd: API_ROOT, stdio: 'inherit' },
    )
    const genMs = Date.now() - tg
    const tu = Date.now()
    doc = await uploadPdfFile(api.apiBase, pdf, 150_000)
    const ingestMs = Date.now() - tu
    const segs = await getSegments(doc)
    const summary = await getDocument(doc)
    console.log(
      `[soak] generated in ${genMs} ms; ingested to ready in ${ingestMs} ms; ` +
        `pages=${summary.page_count} segments=${segs.length} api_sections=${summary.sections.length}`,
    )
    const last = segs.at(-1)!

    // 1. First render (D29).
    await page.goto(`/#/doc/${doc.documentId}`)
    const r1 = await measureRender(page, last.id)
    console.log(
      `[soak] first render: first .seg visible ${r1.firstVisible.toFixed(0)} ms, last .seg ` +
        `attached ${r1.lastAttached.toFixed(0)} ms, .seg elements ${r1.count}`,
    )
    expect(r1.count).toBe(segs.length)
    expect(r1.firstVisible).toBeLessThan(FIRST_RENDER_LIMIT_MS)
    expect(r1.lastAttached).toBeLessThan(FIRST_RENDER_LIMIT_MS)

    // 2. Play; highlighted word matches the FakeBackend clock at 3 s, 8 s, 15 s (PLAY-2).
    await page.getByRole('button', { name: 'Play', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
    const voice = await page.getByLabel('Voice').inputValue()
    const speed = Number(await page.getByLabel('Speed').inputValue())
    const probes: { t: number; elapsed: number; order: number | null; i: number | null }[] = []
    for (const t of [3, 8, 15]) {
      await page.waitForFunction(
        (t) => {
          const h = window.__yomikoe
          return !!h && h.firstStartAt != null && h.now() - h.firstStartAt >= t
        },
        t,
        { timeout: 30_000, polling: 'raf' },
      )
      const a = await activeSeg(page)
      probes.push({ t, elapsed: a.elapsed ?? NaN, order: a.order, i: a.i })
    }
    const probeOk: boolean[] = []
    for (const p of probes) {
      const g = Math.floor(p.elapsed / wordSec(speed))
      const allowed: string[] = []
      for (const d of [-1, 0, 1]) {
        const at = wordAt(segs, g + d)
        if (at)
          allowed.push(`${at.seg.order}:${await tokenForWord(doc, at.seg, at.word, voice, speed)}`)
      }
      const ok = allowed.includes(`${p.order}:${p.i}`)
      probeOk.push(ok)
      console.log(
        `[soak] probe ${p.t} s: elapsed ${p.elapsed.toFixed(3)} s, active ${p.order}:${p.i}, ` +
          `allowed [${allowed.join(', ')}] -> ${ok ? 'pass' : 'fail'}`,
      )
    }
    expect(probeOk, 'probe results at 3 s, 8 s, 15 s').toEqual([true, true, true])

    // 3. Skip to the last section through the Contents list.
    const sections =
      summary.sections.length > 0
        ? summary.sections.map((s) => s.first_segment_id)
        : segs.filter((s) => s.type === 'heading').map((s) => s.id)
    const lastSectionId = sections.at(-1)!
    const lastSectionOrder = segs.find((s) => s.id === lastSectionId)!.order
    await page.getByRole('navigation', { name: 'Contents' }).getByRole('button').last().click()
    await expect
      .poll(async () => (await activeSeg(page)).order, { timeout: 5_000 })
      .toBe(lastSectionOrder)
    await expect(page.locator(`.seg[data-id="${lastSectionId}"]`)).toBeInViewport()
    console.log(
      `[soak] skip to last section: segment ${lastSectionId} (order ${lastSectionOrder} of ` +
        `${segs.length}) active and in viewport`,
    )

    // 4. Pause there, reload, and the position is restored within one sentence (LIB-2).
    await page.waitForTimeout(1_500)
    const before = positionPatches(patches, doc.documentId).length
    await page.getByRole('button', { name: 'Pause', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('paused')
    await expect
      .poll(() => positionPatches(patches, doc!.documentId).length, { timeout: 3_000 })
      .toBeGreaterThan(before)
    const sent = positionPatches(patches, doc.documentId).at(-1)!
    const sentOrder = segs.find((s) => s.id === sent.segment_id)!.order

    await page.reload()
    const r2 = await measureRender(page, last.id)
    await expect(page.locator(`.seg[data-id="${sent.segment_id}"]`)).toBeInViewport()
    const mark = audioRequests.length
    await page.getByRole('button', { name: 'Play', exact: true }).click()
    await expect.poll(() => audioRequests.length - mark, { timeout: 10_000 }).toBeGreaterThan(0)
    const firstId = Number(new URL(audioRequests[mark].url).pathname.split('/').pop())
    const resumedOrder = segs.find((s) => s.id === firstId)!.order
    const delta = Math.abs(resumedOrder - sentOrder)
    console.log(
      `[soak] reload: first .seg visible ${r2.firstVisible.toFixed(0)} ms, last attached ` +
        `${r2.lastAttached.toFixed(0)} ms; saved order ${sentOrder} (offset ${sent.offset_ms} ms), ` +
        `resumed order ${resumedOrder}; restore delta ${delta} sentence(s)`,
    )
    expect(delta).toBeLessThanOrEqual(1)
    await page.getByRole('button', { name: 'Pause', exact: true }).click()
  } finally {
    if (doc) await deleteDocument(doc)
    fs.rmSync(dir, { recursive: true, force: true })
  }
})
