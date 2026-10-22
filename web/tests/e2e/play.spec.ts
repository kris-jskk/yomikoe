/**
 * M3 gate (spec §0, §8 "E2E"): PLAY-1..PLAY-5 against the real API with FakeBackend.
 * Asserted on Chromium; WebKit and Firefox are reported, not asserted, in M3.
 */
import type { Page } from '@playwright/test'
import { PAUSE_MS, pauseAfterMs } from '../../src/player/pauses'
import {
  expect,
  getSegments,
  test,
  wordAt,
  wordAtTime,
  wordSec,
  type Api,
  type Segment,
} from './fixtures'

// WebKit/Firefox run only when YOMIKOE_E2E_ALL_ENGINES=1 (reported, not asserted, in M3).
test.skip(
  ({ browserName }) => browserName !== 'chromium' && !process.env.YOMIKOE_E2E_ALL_ENGINES,
  'M3 gate is asserted on Chromium only',
)
test.describe.configure({ timeout: 90_000 })

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

/**
 * FakeBackend timing rule (api/yomikoe/synthesis/fake.py): every `\S+` word of a segment's
 * normalized_text is round(24000 * 80 ms / speed) frames of silence at 24 kHz, words back to
 * back, clips back to back (an all-silent clip is not trimmed). So elapsed time from the first
 * clip's start maps to (segment order, word index into normalized_text).
 * SYN-8 (spec Q7): each clip is followed by the pause of its block type (pauses.ts: heading, list,
 * equation) before the next one starts; `wordAtTime` adds those gaps.
 */
/** Whitespace tokens of `text` (spec §6 tokenize) and the token holding char offset `c`. */
function tokenIndexAt(text: string, c: number): number {
  const re = /\S+/g
  let i = 0
  for (let m = re.exec(text); m; m = re.exec(text), i++) {
    if (c < m.index + m[0].length) return i
  }
  return i - 1
}

/** Map a normalized_text word index to the DOM token index via the API's X-Timestamps. */
async function tokenForWord(api: Api, seg: Segment, word: number, voice: string, speed: number) {
  const r = await fetch(`${api.apiBase}/audio/${seg.id}?voice=${voice}&speed=${speed.toFixed(2)}`)
  const ts = JSON.parse(r.headers.get('x-timestamps') ?? '[]') as { char_start: number }[]
  return tokenIndexAt(seg.text, ts[Math.min(word, ts.length - 1)].char_start)
}

async function active(page: Page) {
  return page.evaluate(() => {
    const h = window.__yomikoe
    const w = document.querySelector<HTMLElement>('.w.active')
    const seg = w?.closest<HTMLElement>('.seg')
    return {
      elapsed: h && h.firstStartAt != null ? h.now() - h.firstStartAt : null,
      order: seg ? Number(seg.dataset.order) : null,
      i: w ? Number(w.dataset.i) : null,
    }
  })
}

async function openAndPlay(page: Page, api: Api) {
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
}

const activeOrder = (page: Page) =>
  page.evaluate(() => {
    const seg = document.querySelector<HTMLElement>('.w.active')?.closest<HTMLElement>('.seg')
    return seg ? Number(seg.dataset.order) : null
  })

test('harness: the Vite dev server proxies /documents to the e2e API (not 8765)', async ({
  page,
  api,
}) => {
  const r = await page.request.get(`/documents/${api.documentId}`)
  expect(r.status()).toBe(200)
  expect(((await r.json()) as { id: number; status: string }).status).toBe('ready')
})

test('PLAY-1/PLAY-2/PLAY-5: highlighted word matches the FakeBackend clock at 3 s, 8 s, 15 s', async ({
  page,
  api,
}) => {
  const segs = await getSegments(api)
  await openAndPlay(page, api)
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
    const a = await active(page)
    probes.push({ t, elapsed: a.elapsed ?? NaN, order: a.order, i: a.i })
  }
  for (const p of probes) {
    const g = wordAtTime(segs, p.elapsed, wordSec(speed))
    const allowed: string[] = []
    for (const d of [-1, 0, 1]) {
      const at = wordAt(segs, g + d)
      if (at)
        allowed.push(`${at.seg.order}:${await tokenForWord(api, at.seg, at.word, voice, speed)}`)
    }
    expect(allowed, `probe ${p.t} s (elapsed ${p.elapsed.toFixed(3)} s)`).toContain(
      `${p.order}:${p.i}`,
    )
  }
})

test('PLAY-3: clicking the first token of segment order 12 seeks there', async ({
  page,
  api,
  audioRequests,
}) => {
  const segs = await getSegments(api)
  const target = segs.find((s) => s.order === 12)!
  await openAndPlay(page, api)
  await page.locator('.seg[data-order="12"] .w[data-i="0"]').click()
  await expect.poll(() => activeOrder(page), { timeout: 500 }).toBe(12)
  expect(audioRequests.map((r) => new URL(r.url).pathname)).toContain(`/audio/${target.id}`)
})

test('PLAY-4: a speed change mid-play restarts the current sentence at the new speed', async ({
  page,
  api,
  audioRequests,
}) => {
  const segs = await getSegments(api)
  await openAndPlay(page, api)
  // Land the speed change inside a long sentence: wait until the active segment has at least 20
  // tokens and the active token index is in 1..4, then, in the same evaluate, read the order and
  // start recording every (order, token) activation so a 40 ms word is not missed.
  const order = (await (
    await page.waitForFunction(
      () => {
        const w = document.querySelector<HTMLElement>('.w.active')
        const seg = w?.closest<HTMLElement>('.seg')
        if (!w || !seg) return null
        const i = Number(w.dataset.i)
        // i >= 1 so the restart shows up as a transition to token 0 (from 0 to 0 is no mutation).
        if (seg.querySelectorAll('.w').length < 20 || i < 1 || i >= 5) return null
        const seen: string[] = []
        ;(window as unknown as { __seen: string[] }).__seen = seen
        new MutationObserver(() => {
          const a = document.querySelector<HTMLElement>('.w.active')
          const sg = a?.closest<HTMLElement>('.seg')
          if (a && sg) seen.push(`${sg.dataset.order}:${a.dataset.i}`)
        }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] })
        return Number(seg.dataset.order)
      },
      undefined,
      { timeout: 30_000, polling: 'raf' },
    )
  ).jsonValue()) as number
  const current = segs.find((s) => s.order === order)!
  const next = segs.find((s) => s.order === order + 1)!
  const before = audioRequests.length
  await page.getByLabel('Speed').fill('2')
  await expect(page.getByText('2.00x')).toBeVisible({ timeout: 1_000 })
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __seen: string[] }).__seen), {
      timeout: 1_000,
    })
    .toContain(`${order}:0`)
  const after = audioRequests.slice(before).map((r) => new URL(r.url))
  const cur = after.find((u) => u.pathname === `/audio/${current.id}`)
  expect(cur?.searchParams.get('speed')).toBe('2.00')
  await expect
    .poll(
      () =>
        audioRequests
          .slice(before)
          .map((r) => new URL(r.url))
          .find((u) => u.pathname === `/audio/${next.id}`)
          ?.searchParams.get('speed'),
      { timeout: 2_000 },
    )
    .toBe('2.00')
})

test('PLAY-1: pause/resume, next/previous sentence and next/previous section', async ({
  page,
  api,
}) => {
  await openAndPlay(page, api)
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('paused')
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing')

  const o = (await activeOrder(page))!
  await page.getByRole('button', { name: 'Next sentence' }).click()
  await expect.poll(() => activeOrder(page)).toBe(o + 1)
  await page.getByRole('button', { name: 'Previous sentence' }).click()
  await expect.poll(() => activeOrder(page)).toBe(o)

  // Sections are derived client-side from heading segments (spec §7 amendment).
  const headings = await page
    .locator('.seg.seg-heading')
    .evaluateAll((els) => els.map((e) => Number((e as HTMLElement).dataset.order)))
  expect(headings.length).toBeGreaterThan(1)
  const next = headings.filter((h) => h > o)
  expect(next.length).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Next section' }).click()
  await expect.poll(() => activeOrder(page)).toBe(Math.min(...next))

  // Previous section: the current section's heading, or the previous heading if already on one.
  const c = (await activeOrder(page))!
  const prev = headings.filter((h) => (headings.includes(c) ? h < c : h <= c))
  expect(prev.length).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Previous section' }).click()
  await expect.poll(() => activeOrder(page)).toBe(Math.max(...prev))
})

test('PLAY-5: with every clip cached, consecutive entries splice with zero gap', async ({
  page,
  api,
}) => {
  // First play populates the server cache (each GET also synthesizes the next five).
  await openAndPlay(page, api)
  await page.waitForFunction(() => (window.__yomikoe?.entries.length ?? 0) >= 6, undefined, {
    timeout: 30_000,
  })
  // Second play of the same document: every clip is a cache hit.
  await page.reload()
  await openAndPlay(page, api)
  const seen = new Map<number, { segmentId: number; startAt: number; durationSec: number }>()
  await expect
    .poll(
      async () => {
        const entries = await page.evaluate(() => window.__yomikoe?.entries ?? [])
        for (const e of entries) seen.set(e.segmentId, e)
        return seen.size
      },
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(6)
  const sorted = [...seen.values()].sort((a, b) => a.startAt - b.startAt)
  // SYN-8 (Q7): the expected gap is the pause after the preceding segment's block type; 0 for body
  const typeOf = new Map((await getSegments(api)).map((s) => [s.id, s.type]))
  const gaps = sorted.slice(1).map((e, k) => ({
    from: typeOf.get(sorted[k].segmentId) ?? '',
    to: typeOf.get(e.segmentId) ?? '',
    gap: e.startAt - (sorted[k].startAt + sorted[k].durationSec),
  }))
  expect(gaps.length).toBeGreaterThanOrEqual(5)
  for (const g of gaps) expect(Math.abs(g.gap - pauseAfterMs(g.from) / 1000)).toBeLessThan(1e-6)
  // the splice guarantee (body -> body, zero gap) and the heading pause are both measured
  const bodyBody = gaps.filter((g) => g.from === 'body' && g.to === 'body')
  expect(bodyBody.length, 'a body -> body transition').toBeGreaterThan(0)
  for (const g of bodyBody) expect(Math.abs(g.gap)).toBeLessThan(1e-6)
  const headingBody = gaps.filter((g) => g.from === 'heading' && g.to === 'body')
  expect(headingBody.length, 'a heading -> body transition').toBeGreaterThan(0)
  for (const g of headingBody) expect(Math.abs(g.gap - PAUSE_MS.heading / 1000)).toBeLessThan(1e-6)
})
