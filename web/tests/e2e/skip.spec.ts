/**
 * M4 phase 2 (spec §2 "Skip toggles", §5): PLAY-8. With "Skip footnotes" on, footnote segments
 * are dimmed and never fetched. The shared fixture (academic_01) has no footnote or caption
 * segments, so this spec uploads academic_02_memduet (expected.jsonl: 2 footnotes, 9 captions).
 */
import type { Page } from '@playwright/test'
import { expect, getSegments, test, uploadPdf } from './fixtures'

test.describe.configure({ timeout: 150_000 })

const SKIP_PDF = 'academic_02_memduet.pdf'

const activeOrder = (page: Page) =>
  page.evaluate(() => {
    const seg = document.querySelector<HTMLElement>('.w.active')?.closest<HTMLElement>('.seg')
    return seg ? Number(seg.dataset.order) : null
  })

test('PLAY-8: with footnotes skipped, a footnote is dimmed and never requested', async ({
  page,
  api,
  audioRequests,
}) => {
  const doc = await uploadPdf(api.apiBase, SKIP_PDF)
  const segs = await getSegments(doc)
  const footnotes = segs.filter((s) => s.type === 'footnote')
  expect(footnotes.length, `${SKIP_PDF} has footnote segments`).toBeGreaterThan(0)
  const fn = footnotes[0]
  const start = segs.filter((s) => s.order < fn.order && s.type !== 'footnote').at(-2) ?? segs[0]

  await page.goto(`/#/doc/${doc.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.getByLabel('Skip footnotes').check()
  const fnEl = page.locator(`.seg[data-id="${fn.id}"]`)
  await expect(fnEl).toHaveClass(/\bskipped\b/)

  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 10_000 })
  await page.locator(`.seg[data-id="${start.id}"] .w[data-i="0"]`).click()
  await expect
    .poll(async () => (await activeOrder(page)) ?? -1, { timeout: 60_000 })
    .toBeGreaterThan(fn.order)
  const paths = audioRequests.map((r) => new URL(r.url).pathname)
  expect(paths).toContain(`/audio/${start.id}`)
  expect(paths).not.toContain(`/audio/${fn.id}`)
})

test('PLAY-8: the captions toggle dims caption segments', async ({ page, api }) => {
  const doc = await uploadPdf(api.apiBase, SKIP_PDF)
  const caption = (await getSegments(doc)).find((s) => s.type === 'caption')
  expect(caption, `${SKIP_PDF} has caption segments`).toBeTruthy()
  await page.goto(`/#/doc/${doc.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  const el = page.locator(`.seg[data-id="${caption!.id}"]`)
  await expect(el).not.toHaveClass(/\bskipped\b/)
  await page.getByLabel('Skip captions').check()
  await expect(el).toHaveClass(/\bskipped\b/)
})
