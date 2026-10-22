/**
 * PLAY-7 media keys (2026-10-18): after a pause the page must still own the OS media session so
 * the next hardware play key resumes. Hardware keys cannot be simulated, so this probes the parts
 * the page controls: the keep-alive <audio> (one silent looping element, D5/D24) follows the
 * machine, playbackState mirrors it, and the registered media-session handlers pause and resume.
 */
import type { Page } from '@playwright/test'
import { expect, resetState, test, type Api } from './fixtures'

test.describe.configure({ timeout: 90_000 })
test.skip(
  ({ browserName }) => browserName === 'firefox' && !process.env.YOMIKOE_E2E_ALL_ENGINES,
  'Firefox runs only with YOMIKOE_E2E_ALL_ENGINES=1',
)

test.beforeEach(async ({ page, api }) => {
  await resetState(api)
  // Record the handlers the app registers so the test can invoke them like the OS would.
  await page.addInitScript(() => {
    const ms = navigator.mediaSession as MediaSession | undefined
    if (!ms) return
    const store: Record<string, (() => void) | null> = {}
    ;(window as unknown as { __msHandlers: typeof store }).__msHandlers = store
    const orig = ms.setActionHandler.bind(ms)
    ms.setActionHandler = (action, handler) => {
      store[action] = handler as (() => void) | null
      orig(action, handler)
    }
  })
})
test.afterEach(async ({ api }) => {
  await resetState(api)
})

async function open(page: Page, api: Api) {
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
}

const probe = (page: Page) =>
  page.evaluate(() => {
    const els = document.querySelectorAll<HTMLAudioElement>('audio[data-yomikoe-keepalive]')
    return {
      count: els.length,
      paused: els[0]?.paused ?? null,
      loop: els[0]?.loop ?? null,
      muted: els[0]?.muted ?? null,
      playbackState: navigator.mediaSession?.playbackState ?? null,
    }
  })

const invoke = (page: Page, action: string) =>
  page.evaluate((a) => {
    const h = (window as unknown as { __msHandlers?: Record<string, (() => void) | null> })
      .__msHandlers?.[a]
    if (!h) throw new Error(`no media-session handler for ${a}`)
    h()
  }, action)

test('PLAY-7: keep-alive element and playbackState follow play, pause, resume', async ({
  page,
  api,
}) => {
  await open(page, api)
  expect((await probe(page)).count).toBe(0) // created lazily, inside the gesture
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await expect
    .poll(() => probe(page))
    .toEqual({ count: 1, paused: false, loop: true, muted: false, playbackState: 'playing' })

  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('paused')
  await expect
    .poll(() => probe(page))
    .toEqual({ count: 1, paused: true, loop: true, muted: false, playbackState: 'paused' })

  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await expect
    .poll(() => probe(page))
    .toEqual({ count: 1, paused: false, loop: true, muted: false, playbackState: 'playing' })
})

test('PLAY-7: media-session pause then play handlers resume playback', async ({ page, api }) => {
  await open(page, api)
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })

  await invoke(page, 'pause')
  await expect(page.getByRole('status')).toContainText('paused')
  await expect.poll(async () => (await probe(page)).paused).toBe(true)
  expect((await probe(page)).playbackState).toBe('paused')

  await invoke(page, 'play')
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await expect.poll(async () => (await probe(page)).paused).toBe(false)
  expect((await probe(page)).playbackState).toBe('playing')
})
