import { expect, test } from '@playwright/test'

test('app shell renders the heading', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'HearNarro' })).toBeVisible()
})
