/**
 * M4 phase 2 (spec §2 "Position save/restore", "Settings", §5): LIB-2 position saved while
 * playing and on pause, restored across a reload; LIB-3 per-document speed and global default.
 */
import type { Page } from '@playwright/test'
import {
  expect,
  getDocument,
  resetState,
  test,
  DEFAULT_GLOBAL_SETTINGS,
  type Api,
  type PatchLog,
} from './fixtures'

test.skip(({ browserName }) => browserName !== 'chromium', 'M4 phase 2 asserted on Chromium')
test.describe.configure({ timeout: 90_000 })

test.beforeEach(async ({ api }) => {
  await resetState(api)
})
test.afterEach(async ({ api }) => {
  await resetState(api)
})

async function openAndPlay(page: Page, api: Api) {
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
}

type Position = { segment_id: number; offset_ms: number }
const positionPatches = (log: PatchLog, id: number) =>
  log.filter((p) => p.documentId === id && p.body.position).map((p) => p.body.position as Position)

test('LIB-2: position is PATCHed while playing and on pause, and a reload resumes there', async ({
  page,
  api,
  patches,
  audioRequests,
}) => {
  await openAndPlay(page, api)
  await page.waitForTimeout(6_000)
  // Every 5 s while playing (spec §2): at least one position save after 6 s.
  expect(positionPatches(patches, api.documentId).length).toBeGreaterThanOrEqual(1)
  const before = positionPatches(patches, api.documentId).length
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('paused')
  await expect
    .poll(() => positionPatches(patches, api.documentId).length, { timeout: 2_000 })
    .toBeGreaterThan(before)
  const sent = positionPatches(patches, api.documentId).at(-1)!
  expect(typeof sent.segment_id).toBe('number')
  expect(sent.offset_ms).toBeGreaterThanOrEqual(0)
  await expect
    .poll(async () => (await getDocument(api)).position?.segment_id, { timeout: 2_000 })
    .toBe(sent.segment_id)

  await page.reload()
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await expect(page.locator(`.seg[data-id="${sent.segment_id}"]`)).toBeInViewport()
  const mark = audioRequests.length
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect.poll(() => audioRequests.length - mark, { timeout: 10_000 }).toBeGreaterThan(0)
  expect(new URL(audioRequests[mark].url).pathname).toBe(`/audio/${sent.segment_id}`)
})

test('LIB-3: a speed change in the reader PATCHes document settings and survives a reload', async ({
  page,
  api,
  patches,
}) => {
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.getByLabel('Speed').fill('1.5')
  await expect(page.locator('#speed-value')).toHaveText('1.50x')
  await expect
    .poll(
      () =>
        patches
          .filter((p) => p.documentId === api.documentId && p.body.settings)
          .map((p) => (p.body.settings as { speed: number | null }).speed),
      { timeout: 3_000 },
    )
    .toContain(1.5)
  await page.reload()
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await expect(page.locator('#speed-value')).toHaveText('1.50x')
})

test('LIB-3: the library default speed PUTs /settings and a document without settings uses it', async ({
  page,
  api,
}) => {
  await page.goto('/#/')
  await page.getByLabel('Default speed').fill('1.75')
  await expect
    .poll(
      async () =>
        ((await (await fetch(`${api.apiBase}/settings`)).json()) as typeof DEFAULT_GLOBAL_SETTINGS)
          .default_speed,
      { timeout: 3_000 },
    )
    .toBe(1.75)
  // The library's default control never writes an opened document's own settings.
  expect((await getDocument(api)).settings).toEqual({ voice_id: null, speed: null })
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await expect(page.locator('#speed-value')).toHaveText('1.75x')
})
