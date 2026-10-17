// D19: the listener's first-audio wait measured in the built reader (browser end to end).
//
// For each speed, picks three body segments of 100-200 characters whose clip is not cached yet
// (HEAD /audio/{id} -> 404), opens the reader on a fresh page, sets the speed, clicks the
// segment's first word (PLAY from idle, PLAY-3) and records the hook's `hearnarro:first-audio`
// log. A second play of one segment per speed on a fresh page gives the warm (cached) wait.
//
// Usage: API on 8765, Vite on 5180, then
//   node web/scripts/measure_first_audio.mjs
// Env: HN_API (default http://127.0.0.1:8765), HN_WEB (default http://localhost:5180),
//      HN_DOCS (default 16,17,18,19), HN_VOICE (default af_heart).

import { chromium } from 'playwright'

const API = process.env.HN_API ?? 'http://127.0.0.1:8765'
const WEB = process.env.HN_WEB ?? 'http://localhost:5180'
const DOCS = (process.env.HN_DOCS ?? '16,17,18,19').split(',').map(Number)
const VOICE = process.env.HN_VOICE ?? 'af_heart'
const SPEEDS = [0.5, 1.0, 2.0]
const PER_SPEED = 3
const LOOKAHEAD = 6 // server lookahead (5) plus the segment itself

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const audioUrl = (id, speed) => `${API}/audio/${id}?voice=${VOICE}&speed=${speed}`
const isCold = async (id, speed) => (await fetch(audioUrl(id, speed), { method: 'HEAD' })).status === 404

async function segmentsOf(docId) {
  const r = await fetch(`${API}/documents/${docId}/segments?from=0&limit=500`)
  return (await r.json()).segments
}

/** Wait until the server's lookahead after `seg` has finished, so it does not compete with the next run. */
async function waitLookahead(all, seg, speed) {
  const i = all.findIndex((s) => s.id === seg.id)
  const ids = all.slice(i, i + LOOKAHEAD).map((s) => s.id)
  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    const cold = await Promise.all(ids.map((id) => isCold(id, speed)))
    if (!cold.some(Boolean)) return
    await sleep(1000)
  }
}

async function measure(browser, docId, seg, speed) {
  const page = await browser.newPage()
  let log = null
  page.on('console', async (msg) => {
    if (msg.type() !== 'info' || !msg.text().startsWith('hearnarro:first-audio')) return
    const args = msg.args()
    if (args.length > 1) log = await args[1].jsonValue()
  })
  await page.goto(`${WEB}/#/doc/${docId}`)
  const token = page.locator(`.seg[data-id="${seg.id}"] .w`).first()
  await token.waitFor({ state: 'attached', timeout: 30000 })
  await page.locator('#speed').evaluate((el, v) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    set.call(el, String(v))
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
  }, speed)
  const shown = await page.locator('#speed-value').textContent()
  await token.scrollIntoViewIfNeeded()
  await token.click()
  const deadline = Date.now() + 60000
  while (log === null && Date.now() < deadline) await sleep(50)
  const status = await page.locator('[role=status]').getAttribute('data-status')
  await page.close()
  return { log, shown, status }
}

async function main() {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] })
  const docs = new Map()
  for (const d of DOCS) docs.set(d, await segmentsOf(d))
  const pool = []
  for (const [docId, segs] of docs)
    for (const s of segs)
      if (s.type === 'body' && s.text.length >= 100 && s.text.length <= 200) pool.push({ docId, seg: s })
  // interleave documents and space picks apart so lookahead never warms a later pick
  pool.sort((a, b) => a.seg.order - b.seg.order || a.docId - b.docId)
  const used = new Set()
  const rows = []
  for (const speed of SPEEDS) {
    let taken = 0
    let warmTarget = null
    for (const { docId, seg } of pool) {
      if (taken >= PER_SPEED) break
      if ([...used].some((u) => u.docId === docId && Math.abs(u.order - seg.order) < 15)) continue
      if (!(await isCold(seg.id, speed))) continue
      used.add({ docId, order: seg.order })
      const r = await measure(browser, docId, seg, speed)
      const head = await fetch(audioUrl(seg.id, speed), { method: 'HEAD' })
      const dur = head.headers.get('x-duration-ms')
      rows.push({ speed, docId, seg, cache: 'cold', r, dur })
      console.error(`speed ${speed} doc ${docId} seg ${seg.id}: ${JSON.stringify(r.log)}`)
      warmTarget ??= { docId, seg, dur }
      taken++
      await waitLookahead(docs.get(docId), seg, speed)
    }
    if (warmTarget) {
      const r = await measure(browser, warmTarget.docId, warmTarget.seg, speed)
      rows.push({ speed, docId: warmTarget.docId, seg: warmTarget.seg, cache: 'warm', r, dur: warmTarget.dur })
      console.error(`speed ${speed} warm seg ${warmTarget.seg.id}: ${JSON.stringify(r.log)}`)
    }
  }
  await browser.close()

  console.log(`Voice ${VOICE}; web ${WEB}; api ${API}; ${new Date().toISOString()}\n`)
  console.log('| speed | doc | segment | text len | cache before | first-audio ms | logged segment | logged speed | X-Duration-Ms | status after | < 2000 ms |')
  console.log('|---|---|---|---|---|---|---|---|---|---|---|')
  for (const { speed, docId, seg, cache, r, dur } of rows) {
    const l = r.log
    const okSeg = l && l.segmentId === seg.id ? `${l.segmentId}` : `MISMATCH ${l?.segmentId}`
    console.log(
      `| ${speed} | ${docId} | ${seg.id} | ${seg.text.length} | ${cache === 'cold' ? 'cold (HEAD 404)' : 'warm (2nd play)'} | ${l ? l.ms : 'none'} | ${okSeg} | ${l?.speed ?? '-'} (${r.shown}) | ${dur ?? '-'} | ${r.status} | ${l ? (l.ms < 2000 ? 'yes' : 'NO') : '-'} |`,
    )
  }
  for (const speed of SPEEDS) {
    const cold = rows.filter((x) => x.speed === speed && x.cache === 'cold' && x.r.log).map((x) => x.r.log.ms)
    if (cold.length)
      console.log(`\nspeed ${speed}: cold mean ${Math.round(cold.reduce((a, b) => a + b, 0) / cold.length)} ms, worst ${Math.max(...cold)} ms (n=${cold.length})`)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
