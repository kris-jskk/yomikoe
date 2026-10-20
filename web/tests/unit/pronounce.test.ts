// TERM-2: pronunciation overrides in the reader. Client calls against the real route bodies
// (_agent/results/1026_routes.md), the dialog's save path and markup, the invalidated-segment
// helper, and the engine dropping prefetched clips so the next play refetches them.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  apiErrorDetail,
  deletePronunciation,
  listPronunciations,
  putPronunciation,
} from '../../src/api/client'
import type { Pronunciation, PronunciationSaved, Segment } from '../../src/api/types'
import {
  PronounceDialog,
  pickWord,
  segmentsWithWord,
  submitPronunciation,
} from '../../src/components/PronounceDialog'
import { initialState, type PlayerEvent } from '../../src/player/machine'
import { PlayerEngine } from '../../src/player/usePlayer'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const ROW: Pronunciation = {
  id: 1,
  document_id: 1,
  word: 'navier',
  respelling: 'nav-YAY',
  created_at: '2026-10-20T16:03:47+00:00',
}

const UNPROCESSABLE = {
  detail: [
    {
      type: 'value_error',
      loc: ['body', 'respelling'],
      msg: 'Value error, respelling must contain a letter',
      input: '12 -',
      ctx: { error: {} },
    },
  ],
}

describe('TERM-2 client', () => {
  it('listPronunciations: GET /pronunciations?document_id=N, or no query for global', async () => {
    fetchMock.mockResolvedValueOnce(json([ROW]))
    expect(await listPronunciations(1)).toEqual([ROW])
    expect(String(fetchMock.mock.calls[0][0])).toBe('/pronunciations?document_id=1')
    fetchMock.mockResolvedValueOnce(json([]))
    expect(await listPronunciations(null)).toEqual([])
    expect(String(fetchMock.mock.calls[1][0])).toBe('/pronunciations')
  })

  it('putPronunciation: PUT JSON body with document_id (null = global), returns invalidated', async () => {
    const saved: PronunciationSaved = { ...ROW, invalidated: 2 }
    fetchMock.mockResolvedValueOnce(json(saved))
    const got = await putPronunciation({ document_id: 1, word: 'Navier', respelling: 'nav-YAY' })
    expect(got.invalidated).toBe(2)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/pronunciations')
    expect(init?.method).toBe('PUT')
    expect(JSON.parse(String(init?.body))).toEqual({
      document_id: 1,
      word: 'Navier',
      respelling: 'nav-YAY',
    })
    fetchMock.mockResolvedValueOnce(json({ ...saved, document_id: null }))
    await putPronunciation({ document_id: null, word: 'prose', respelling: 'prohz' })
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body)).document_id).toBeNull()
  })

  it('deletePronunciation: DELETE /pronunciations/{id} -> {invalidated}', async () => {
    fetchMock.mockResolvedValueOnce(json({ invalidated: 0 }))
    expect(await deletePronunciation(1)).toEqual({ invalidated: 0 })
    expect(fetchMock.mock.calls[0][0]).toBe('/pronunciations/1')
    expect(fetchMock.mock.calls[0][1]?.method).toBe('DELETE')
  })

  it('a 422 keeps the body; apiErrorDetail gives the server message', async () => {
    fetchMock.mockResolvedValueOnce(json(UNPROCESSABLE, 422))
    const err = await putPronunciation({ document_id: 1, word: 'eta', respelling: '12 -' }).catch(
      (e: unknown) => e,
    )
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(422)
    expect(apiErrorDetail(err)).toBe('respelling must contain a letter')
    expect(apiErrorDetail(new ApiError(404, '/x', '404', JSON.stringify({ detail: 'nope' })))).toBe(
      'nope',
    )
  })
})

describe('TERM-2 PronounceDialog', () => {
  it('renders the word, a respelling input, the two scopes, Save and Listen', () => {
    const html = renderToStaticMarkup(
      createElement(PronounceDialog, {
        word: 'Navier',
        documentId: 1,
        onSaved: () => {},
        onListen: () => {},
        onClose: () => {},
      }),
    )
    expect(html).toContain('Pronounce as')
    expect(html).toContain('Navier')
    expect(html).toMatch(/<input[^>]*aria-label="Respelling"/)
    expect(html).toContain('this document')
    expect(html).toContain('all documents')
    expect(html).toMatch(/<button[^>]*>Save<\/button>/)
    expect(html).toMatch(/<button[^>]*>Listen<\/button>/)
  })

  it('submitPronunciation sends the chosen scope', async () => {
    const put = vi.fn(async () => ({ ...ROW, invalidated: 3 }))
    const doc = await submitPronunciation(put, 7, 'document', 'Navier', 'nav-YAY')
    expect(put).toHaveBeenLastCalledWith({ document_id: 7, word: 'Navier', respelling: 'nav-YAY' })
    expect(doc).toEqual({ ok: true, saved: { ...ROW, invalidated: 3 } })
    await submitPronunciation(put, 7, 'global', 'Navier', 'nav-YAY')
    expect(put).toHaveBeenLastCalledWith({
      document_id: null,
      word: 'Navier',
      respelling: 'nav-YAY',
    })
  })

  it("a 422 becomes the dialog's error text (the server's message)", async () => {
    const put = vi.fn(async () => {
      throw new ApiError(422, '/pronunciations', '422', JSON.stringify(UNPROCESSABLE))
    })
    expect(await submitPronunciation(put, 1, 'document', 'eta', '12 -')).toEqual({
      ok: false,
      error: 'respelling must contain a letter',
    })
  })

  it('pickWord strips punctuation from the selection', () => {
    expect(pickWord('  Navier–Stokes, ')).toBe('Navier')
    expect(pickWord('(eta)')).toBe('eta')
    expect(pickWord(' , ')).toBeNull()
  })
})

const seg = (id: number, normalized_text: string): Segment => ({
  id,
  order: id,
  block_id: 1,
  type: 'body',
  section_id: null,
  text: normalized_text,
  normalized_text,
  char_start: 0,
  char_end: normalized_text.length,
})

describe('TERM-2 invalidated segments', () => {
  it('segmentsWithWord: whole token, case-insensitive, on normalized_text', () => {
    const segs = [
      seg(100, 'The Navier equations.'),
      seg(101, 'navier, again'),
      seg(102, 'Naviers are not a match'),
      seg(103, 'nothing here'),
    ]
    expect(segmentsWithWord(segs, 'Navier')).toEqual([100, 101])
    expect(segmentsWithWord(segs, 'a.b')).toEqual([])
  })

  it('PlayerEngine.dropClips aborts and forgets the prefetched clips of those segments only', () => {
    const engine = new PlayerEngine(
      () => {},
      () => {},
    )
    const mk = () => ({ key: 'af_heart@1.25', ctrl: new AbortController(), clip: null })
    const a = mk()
    const b = mk()
    const c = mk()
    engine.pending.set(100, a)
    engine.pending.set(101, b)
    engine.pending.set(102, c)
    engine.dropClips([100, 102, 999])
    expect([...engine.pending.keys()]).toEqual([101])
    expect(a.ctrl.signal.aborted).toBe(true)
    expect(c.ctrl.signal.aborted).toBe(true)
    expect(b.ctrl.signal.aborted).toBe(false)
  })

  it('a dropped clip while playing rebuilds through SEEK at the current position', () => {
    const events: PlayerEvent[] = []
    const engine = new PlayerEngine(
      (e) => events.push(e),
      () => {},
    )
    engine.sync({ ...initialState, status: 'playing', current: { segmentId: 100, offsetMs: 300 } })
    engine.builtKey = 'af_heart@1.25'
    engine.pending.set(101, { key: 'af_heart@1.25', ctrl: new AbortController(), clip: null })
    engine.dropClips([103])
    expect(events).toEqual([]) // nothing of 103 held: no rebuild
    engine.dropClips([101])
    expect(events).toEqual([{ type: 'SEEK', segmentId: 100, offsetMs: 300 }])
  })

  it('a dropped clip while paused makes the next play a PLAY (rebuild), not a RESUME', () => {
    const events: PlayerEvent[] = []
    const engine = new PlayerEngine(
      (e) => events.push(e),
      () => {},
    )
    engine.sync({ ...initialState, status: 'paused', current: { segmentId: 100, offsetMs: 300 } })
    engine.builtKey = 'af_heart@1.25'
    engine.entries.set(100, {
      segmentId: 100,
      source: null,
      startAt: 0,
      durationSec: 5,
      generation: 0,
      mapped: [],
    })
    engine.dropClips([100])
    expect(events).toEqual([])
    expect(engine.builtKey).toBe('') // play() compares it with the settings key and sends PLAY
  })
})
