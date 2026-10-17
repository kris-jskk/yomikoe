/**
 * Browser decode matrix (spec §8, D16): decodeAudioData on tone.wav and tone.ogg (1 s 440 Hz,
 * made by fixtures/make_tone.py with the API's WavEncoder / OpusEncoder) in every project.
 * Asserted: WAV on Chromium. Everything else is reported (DECODE lines + annotations).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures')
const FORMATS = [
  { file: 'tone.wav', type: 'audio/wav' },
  { file: 'tone.ogg', type: 'audio/ogg' },
].filter((f) => fs.existsSync(path.join(FIXTURES, f.file)))

test.beforeEach(async ({ page }) => {
  await page.route('**/__fixtures/*', (route) => {
    const name = path.basename(new URL(route.request().url()).pathname)
    const f = FORMATS.find((x) => x.file === name)
    return f
      ? route.fulfill({ path: path.join(FIXTURES, f.file), contentType: f.type })
      : route.fulfill({ status: 404 })
  })
  await page.goto('/')
})

for (const { file } of FORMATS) {
  test(`decode ${file}`, async ({ page, browserName }) => {
    const r = await page.evaluate(async (url) => {
      const ctx = new AudioContext()
      try {
        const bytes = await (await fetch(url)).arrayBuffer()
        const b = await ctx.decodeAudioData(bytes)
        return { ok: true, duration: b.duration, sampleRate: b.sampleRate, error: '' }
      } catch (e) {
        return { ok: false, duration: 0, sampleRate: 0, error: String(e) }
      } finally {
        await ctx.close()
      }
    }, `/__fixtures/${file}`)
    const line = `DECODE ${browserName} ${file} ${r.ok ? 'pass' : 'fail'} duration=${r.duration.toFixed(4)} s rate=${r.sampleRate} ${r.error}`
    console.log(line)
    test.info().annotations.push({ type: 'decode', description: line })
    if (browserName === 'chromium' && file === 'tone.wav') {
      expect(r.ok).toBe(true)
      expect(r.duration).toBeCloseTo(1, 2)
    }
  })
}

test('AudioContext.currentTime advances headless while a buffer plays', async ({
  page,
  browserName,
}) => {
  const r = await page.evaluate(async () => {
    const ctx = new AudioContext()
    const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    await ctx.resume()
    const t0 = ctx.currentTime
    src.start()
    await new Promise((res) => setTimeout(res, 700))
    const out = { state: ctx.state, advanced: ctx.currentTime - t0 }
    await ctx.close()
    return out
  })
  const line = `CLOCK ${browserName} state=${r.state} advanced=${r.advanced.toFixed(3)} s in 0.700 s`
  console.log(line)
  test.info().annotations.push({ type: 'clock', description: line })
  if (browserName === 'chromium') expect(r.advanced).toBeGreaterThan(0.3)
})
