/**
 * M4 phase 2 (spec §2 "Keyboard", §5): PLAY-6 keyboard shortcuts on the reader. Keys go to the
 * document (nothing focused) so a focused button never turns Space into a click.
 */
import type { Page } from '@playwright/test'
import { expect, resetState, test, type Api } from './fixtures'

test.skip(({ browserName }) => browserName !== 'chromium', 'M4 phase 2 asserted on Chromium')
test.describe.configure({ timeout: 90_000 })

test.beforeEach(async ({ api }) => {
  await resetState(api)
})
test.afterEach(async ({ api }) => {
  await resetState(api)
})

async function open(page: Page, api: Api) {
  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
}

const activeOrder = (page: Page) =>
  page.evaluate(() => {
    const seg = document.querySelector<HTMLElement>('.w.active')?.closest<HTMLElement>('.seg')
    return seg ? Number(seg.dataset.order) : null
  })

const speedShown = async (page: Page) =>
  Number((await page.locator('#speed-value').innerText()).replace('x', ''))

test('PLAY-6: Space toggles play and pause', async ({ page, api }) => {
  await open(page, api)
  await page.keyboard.press('Space')
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await page.keyboard.press('Space')
  await expect(page.getByRole('status')).toContainText('paused')
})

test('PLAY-6: ArrowRight moves to the next sentence', async ({ page, api }) => {
  await open(page, api)
  await page.keyboard.press('Space')
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await expect.poll(() => activeOrder(page), { timeout: 10_000 }).not.toBeNull()
  const o = (await activeOrder(page))!
  await page.keyboard.press('ArrowRight')
  await expect.poll(() => activeOrder(page)).toBe(o + 1)
})

test('PLAY-6: + raises the speed by 0.25', async ({ page, api }) => {
  await open(page, api)
  const s = await speedShown(page)
  await page.keyboard.press('+')
  await expect(page.locator('#speed-value')).toHaveText(`${(s + 0.25).toFixed(2)}x`)
})

test('PLAY-6: keys are ignored while the voice select has focus', async ({ page, api }) => {
  await open(page, api)
  // The shortcut works with nothing focused...
  const s = await speedShown(page)
  await page.keyboard.press('+')
  await expect(page.locator('#speed-value')).toHaveText(`${(s + 0.25).toFixed(2)}x`)
  // ...and does nothing while the voice select has focus.
  await page.getByLabel('Voice').focus()
  await page.keyboard.press('+')
  await page.keyboard.press('Space')
  await page.waitForTimeout(500)
  await expect(page.locator('#speed-value')).toHaveText(`${(s + 0.25).toFixed(2)}x`)
  await expect(page.getByRole('status')).not.toContainText('playing')
})
