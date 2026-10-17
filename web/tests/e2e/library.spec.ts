/**
 * M4 phase 2 (spec §2 "Library", §5): LIB-1 list fields and row navigation, LIB-4 delete with an
 * inline confirm. Runs against the e2e API (FakeBackend) from fixtures.ts.
 */
import { expect, listDocuments, resetState, test, uploadPdf } from './fixtures'

test.skip(({ browserName }) => browserName !== 'chromium', 'M4 phase 2 asserted on Chromium')
test.describe.configure({ timeout: 120_000 })

/** A second, small fixture PDF used only by the delete test, so the shared document survives. */
const DELETE_PDF = 'report_05_controls.pdf'

test.beforeEach(async ({ api }) => {
  await resetState(api)
})

test('LIB-1: the library row shows title, pages, 0% progress and status; a click opens the reader', async ({
  page,
  api,
}) => {
  const summary = (await listDocuments(api.apiBase)).find((d) => d.id === api.documentId)!
  expect(summary.title).toBeTruthy()
  await page.goto('/#/')
  await expect(page.getByTestId('library')).toBeVisible()
  const row = page.getByTestId(`doc-row-${api.documentId}`)
  await expect(row).toBeVisible()
  await expect(row.getByTestId('doc-title')).toHaveText(summary.title!)
  await expect(row.getByTestId('doc-pages')).toHaveText(String(summary.page_count))
  await expect(row.getByTestId('doc-progress')).toHaveText('0%')
  await expect(row.getByTestId('doc-status')).toHaveText('ready')
  await row.getByTestId('doc-title').click()
  await expect(page).toHaveURL(new RegExp(`#/doc/${api.documentId}$`))
  await expect(page.locator('.seg[data-order]').first()).toBeVisible()
})

test('LIB-4: delete with an inline confirm removes the row and the document', async ({
  page,
  api,
}) => {
  const victim = await uploadPdf(api.apiBase, DELETE_PDF)
  expect(victim.documentId).not.toBe(api.documentId)
  await page.goto('/#/')
  const row = page.getByTestId(`doc-row-${victim.documentId}`)
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Delete', exact: true }).click()
  // Inline confirm: nothing is deleted until the confirm button is pressed.
  expect((await listDocuments(api.apiBase)).map((d) => d.id)).toContain(victim.documentId)
  await row.getByRole('button', { name: 'Confirm delete', exact: true }).click()
  await expect(row).toHaveCount(0)
  await expect
    .poll(async () => (await listDocuments(api.apiBase)).map((d) => d.id))
    .not.toContain(victim.documentId)
  // The shared document is untouched.
  await expect(page.getByTestId(`doc-row-${api.documentId}`)).toBeVisible()
})
