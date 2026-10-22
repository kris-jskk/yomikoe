/**
 * M5 phase 5 (spec _agent/specs/m5-academic-reading.md §4d, §8 Q7) on a formula fixture:
 * MATH-5 an equation segment is highlighted whole and its maths ranges render unsplit and boxed;
 * PLAY-10 e / r and the PlayerBar buttons skip past and repeat the equation run;
 * PLAY-11 equation clips are requested at speed x equation_speed_factor, prose at the document speed,
 * and the PlayerBar select saves the factor through PUT /settings. No engine skips (D22).
 */
import type { Page } from '@playwright/test'
import {
  deleteDocument,
  expect,
  getSegments,
  resetState,
  test,
  uploadPdf,
  type Api,
  type Segment,
} from './fixtures'

const PDF = 'formula_01_pfn_bayes.pdf'

test.describe.configure({ timeout: 120_000 })

let doc: Api | null = null
let segs: Segment[] = []

test.beforeAll(async ({ api }) => {
  doc = await uploadPdf(api.apiBase, PDF)
  segs = await getSegments(doc)
})
test.afterAll(async () => {
  if (doc) await deleteDocument(doc)
})
test.beforeEach(async ({ api }) => {
  await resetState(api)
})
test.afterEach(async ({ api }) => {
  await resetState(api)
})

type Hooks = { entries: { segmentId: number }[] }
type Sample = { id: number | null; words: number }

/** Equation runs as [first index, last index] into `segs`, each followed by at least one segment. */
function equationRuns(): [number, number][] {
  const runs: [number, number][] = []
  for (let i = 0; i < segs.length; i++) {
    if (segs[i].type !== 'equation') continue
    let j = i
    while (j + 1 < segs.length && segs[j + 1].type === 'equation') j++
    if (j + 1 < segs.length) runs.push([i, j])
    i = j
  }
  return runs
}

async function open(page: Page) {
  await page.goto(`/#/doc/${doc!.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  // sample the highlight every frame: which .seg is active and how many .w.active it holds
  await page.evaluate(() => {
    const w = window as unknown as { __samples: Sample[] }
    w.__samples = []
    const f = () => {
      const a = document.querySelector<HTMLElement>('.seg.active')
      w.__samples.push({
        id: a ? Number(a.dataset.id) : null,
        words: a ? a.querySelectorAll('.w.active').length : 0,
      })
      requestAnimationFrame(f)
    }
    requestAnimationFrame(f)
  })
}

const seg = (page: Page, id: number) => page.locator(`.seg[data-id="${id}"]`)
const samples = (page: Page) =>
  page.evaluate(() => (window as unknown as { __samples: Sample[] }).__samples)
const firstEntry = (page: Page) =>
  page.evaluate(
    () => (window as unknown as { __yomikoe?: Hooks }).__yomikoe?.entries[0]?.segmentId ?? null,
  )
const activeId = (page: Page) =>
  page.evaluate(() => {
    const a = document.querySelector<HTMLElement>('.seg.active')
    return a ? Number(a.dataset.id) : null
  })

/** Click segment `id`, wait until it plays, then pause on it (Space). */
async function playThenPause(page: Page, id: number) {
  await seg(page, id).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 15_000 })
  await expect.poll(() => activeId(page), { timeout: 10_000 }).toBe(id)
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  await page.keyboard.press('Space')
  await expect(page.getByRole('status')).toContainText('paused')
}

const speedOf = (url: string) => Number(new URL(url).searchParams.get('speed'))

test('MATH-5: an equation segment is highlighted whole; its maths ranges are unsplit and boxed', async ({
  page,
}) => {
  const eqs = segs.filter((s) => s.type === 'equation')
  expect(eqs.length, `${PDF} has equation segments`).toBeGreaterThan(0)
  const eq = eqs.find((s) => (s.math ?? []).length > 0) ?? eqs[0]
  const ranges = eq.math ?? []
  expect(ranges.length, 'the equation segment carries maths ranges').toBeGreaterThan(0)
  await open(page)
  const maths = seg(page, eq.id).locator('.math')
  await expect(maths).toHaveCount(ranges.length)
  await expect(seg(page, eq.id).locator('.math .w')).toHaveCount(0)
  for (let k = 0; k < ranges.length; k++) {
    const m = maths.nth(k)
    await expect(m).toHaveText(eq.text.slice(ranges[k].start, ranges[k].end).trim())
    const border = await m.evaluate((el) => getComputedStyle(el).borderTopStyle)
    expect(border, 'maths range is boxed').not.toBe('none')
  }
  await seg(page, eq.id).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 15_000 })
  await expect
    .poll(async () => (await samples(page)).some((s) => s.id === eq.id), { timeout: 10_000 })
    .toBe(true)
  const onEq = (await samples(page)).filter((s) => s.id === eq.id)
  expect(
    onEq.every((s) => s.words === 0),
    'no word-level highlight inside the equation',
  ).toBe(true)
  await expect(seg(page, eq.id)).toHaveClass(/active/)
})

test('PLAY-10: r returns to the start of the equation run and e moves past it (keys and buttons)', async ({
  page,
}) => {
  const runs = equationRuns()
  expect(runs.length, `${PDF} has an equation run with a segment after it`).toBeGreaterThan(0)
  const [a, b] = runs.reduce((x, y) => (y[1] - y[0] > x[1] - x[0] ? y : x))
  const start = segs[a].id
  const last = segs[b].id
  const after = segs[b + 1].id
  await open(page)

  // keys
  await playThenPause(page, last)
  await expect(page.locator('#skip-equation')).toBeEnabled()
  await page.keyboard.press('r')
  await expect.poll(() => firstEntry(page), { timeout: 15_000 }).toBe(start)
  await page.keyboard.press('e')
  await expect.poll(() => firstEntry(page), { timeout: 15_000 }).toBe(after)

  // buttons
  await playThenPause(page, last)
  await page.locator('#repeat-equation').click()
  await expect.poll(() => firstEntry(page), { timeout: 15_000 }).toBe(start)
  await page.locator('#skip-equation').click()
  await expect.poll(() => firstEntry(page), { timeout: 15_000 }).toBe(after)
})

test('PLAY-10: the equation buttons are disabled on a prose segment', async ({ page }) => {
  const body = segs.find((s) => s.type === 'body')!
  await open(page)
  await playThenPause(page, body.id)
  await expect(page.locator('#skip-equation')).toBeDisabled()
  await expect(page.locator('#repeat-equation')).toBeDisabled()
})

test('PLAY-11: an equation clip is requested at speed x 0.8, a prose clip at the document speed', async ({
  page,
  audioRequests,
}) => {
  const eq = segs.find((s) => s.type === 'equation')!
  const body = segs.find((s) => s.type === 'body')!
  await open(page)
  const docSpeed = Number((await page.locator('#speed-value').innerText()).replace('x', ''))
  await expect(page.locator('#equation-speed')).toHaveValue('0.80')
  await seg(page, eq.id).click()
  const reqs = (id: number) =>
    audioRequests.filter((r) => new URL(r.url).pathname === `/audio/${id}`).map((r) => r.url)
  await expect.poll(() => reqs(eq.id).length, { timeout: 15_000 }).toBeGreaterThan(0)
  const want = Math.round(docSpeed * 0.8 * 20) / 20
  for (const u of reqs(eq.id)) expect(speedOf(u)).toBeCloseTo(want, 5)
  await seg(page, body.id).click()
  await expect.poll(() => reqs(body.id).length, { timeout: 15_000 }).toBeGreaterThan(0)
  for (const u of reqs(body.id)) expect(speedOf(u)).toBeCloseTo(docSpeed, 5)
})

test('PLAY-11: the equation-speed select saves equation_speed_factor through PUT /settings', async ({
  page,
  audioRequests,
}) => {
  const puts: Record<string, unknown>[] = []
  page.on('request', (req) => {
    if (req.method() === 'PUT' && new URL(req.url()).pathname === '/settings')
      puts.push((req.postDataJSON() as Record<string, unknown>) ?? {})
  })
  const eq = segs.find((s) => s.type === 'equation')!
  await open(page)
  const docSpeed = Number((await page.locator('#speed-value').innerText()).replace('x', ''))
  await page.locator('#equation-speed').selectOption('0.60')
  await expect.poll(() => puts.length, { timeout: 10_000 }).toBeGreaterThan(0)
  expect(puts[puts.length - 1].equation_speed_factor).toBeCloseTo(0.6, 5)
  await seg(page, eq.id).click()
  const reqs = () =>
    audioRequests.filter((r) => new URL(r.url).pathname === `/audio/${eq.id}`).map((r) => r.url)
  await expect.poll(() => reqs().length, { timeout: 15_000 }).toBeGreaterThan(0)
  expect(speedOf(reqs()[reqs().length - 1])).toBeCloseTo(Math.round(docSpeed * 0.6 * 20) / 20, 5)
  // the factor is global: a reload reads it back from GET /settings
  await page.reload()
  await expect(page.locator('#equation-speed')).toHaveValue('0.60')
})
