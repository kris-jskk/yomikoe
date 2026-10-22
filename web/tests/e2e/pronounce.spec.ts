/**
 * M5 phase 4 (spec _agent/specs/m5-academic-reading.md §4b "Web", §5): TERM-2. Select a word in the
 * reader, save a respelling for this document through "Pronounce as", and the sentence's clip is
 * requested again on the next play (the prefetched/scheduled clip was dropped). A 422 shows the
 * server's message in the dialog. Runs on every engine (no engine skip; supervisor-log 2026-10-17).
 */
import type { Page } from '@playwright/test'
import { expect, getSegments, test, type Segment } from './fixtures'

test.describe.configure({ timeout: 120_000 })

const WORD = /^[A-Za-z]{4,}$/

/** First token index of `seg.text` that is a plain word also present as a token of normalized_text. */
function wordIndex(seg: Segment): number {
  const norm = new Set(seg.normalized_text.toLowerCase().split(/[^a-z]+/))
  const toks = seg.text.split(/\s+/).filter((t) => t !== '')
  return toks.findIndex((t) => WORD.test(t) && norm.has(t.toLowerCase()))
}

/** Select the whole `.w` span (a word selection, the same in every engine). */
async function selectWord(page: Page, segId: number, i: number) {
  await page.evaluate(
    ([id, idx]) => {
      const el = document.querySelector(`.seg[data-id="${id}"] .w[data-i="${idx}"]`)
      if (!el) throw new Error(`no word ${id}:${idx}`)
      const range = document.createRange()
      range.selectNodeContents(el)
      const sel = window.getSelection()!
      sel.removeAllRanges()
      sel.addRange(range)
    },
    [segId, i] as const,
  )
}

const activeId = (page: Page) =>
  page.evaluate(() => {
    const seg = document.querySelector<HTMLElement>('.seg.active')
    return seg ? Number(seg.dataset.id) : null
  })

test('TERM-2: a saved respelling makes the next play request the sentence again', async ({
  page,
  api,
  audioRequests,
}) => {
  const segs = (await getSegments(api)).filter((s) => wordIndex(s) >= 0)
  expect(segs.length, 'segments with a plain word').toBeGreaterThan(3)
  const start = segs[0]
  const byId = new Map(segs.map((s) => [s.id, s]))

  await page.goto(`/#/doc/${api.documentId}`)
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
  await page.locator(`.seg[data-id="${start.id}"] .w[data-i="0"]`).click()
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 15_000 })
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('paused')

  // the sentence the listener is on: its clip is scheduled, so a plain resume would not refetch it
  const curId = (await activeId(page)) ?? start.id
  const cur = byId.get(curId) ?? start
  const i = wordIndex(cur)
  expect(i, `segment ${cur.id} has a plain word`).toBeGreaterThanOrEqual(0)
  const word = cur.text.split(/\s+/).filter((t) => t !== '')[i]
  const fetched = () =>
    audioRequests.filter((r) => new URL(r.url).pathname === `/audio/${cur.id}`).length
  const before = fetched()
  expect(before, `/audio/${cur.id} requested once while playing`).toBeGreaterThanOrEqual(1)

  await selectWord(page, cur.id, i)
  await page.getByRole('button', { name: 'Pronounce as' }).click()
  const dialog = page.getByRole('dialog', { name: 'Pronounce as' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText(word)

  // a respelling without a letter: the server's 422 message is shown in the dialog
  await dialog.getByLabel('Respelling').fill('12 -')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog.getByRole('alert')).toContainText('respelling must contain a letter')

  await dialog.getByLabel('this document').check()
  await dialog.getByLabel('Respelling').fill('zoh-RAH')
  const put = page.waitForResponse(
    (r) => new URL(r.url()).pathname === '/pronunciations' && r.request().method() === 'PUT',
  )
  await dialog.getByRole('button', { name: 'Save' }).click()
  const res = await put
  expect(res.status()).toBe(200)
  const body = (await res.json()) as { document_id: number | null; invalidated: number }
  expect(body.document_id).toBe(api.documentId)
  expect(body.invalidated).toBeGreaterThanOrEqual(1)
  await expect(dialog.getByRole('status')).toContainText('Saved')
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()

  // the next play rebuilds the schedule and asks for the sentence again
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect.poll(fetched, { timeout: 15_000 }).toBeGreaterThan(before)
  await expect(page.getByRole('status')).toContainText('playing', { timeout: 15_000 })

  // Listen plays the selected sentence through the player (no <audio> per segment, D5)
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  await selectWord(page, cur.id, i)
  await page.getByRole('button', { name: 'Pronounce as' }).click()
  const again = fetched()
  await dialog.getByLabel('Respelling').fill('zoh-RAH')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog.getByRole('status')).toContainText('Saved')
  await dialog.getByRole('button', { name: 'Listen' }).click()
  await expect.poll(fetched, { timeout: 15_000 }).toBeGreaterThan(again)
  const playerStatus = page.getByRole('region', { name: 'Player' }).getByRole('status')
  await expect(playerStatus).toContainText(/playing|loading/, { timeout: 15_000 })
  expect(await page.locator('audio:not([loop])').count()).toBe(0)
})
