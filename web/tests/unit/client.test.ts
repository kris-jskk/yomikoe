// PLAY-1/PLAY-4: typed API client (spec §1, §4) against a mocked fetch and a fake decodeAudioData.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  TIMEOUT_MS,
  audioUrl,
  deleteDocument,
  fetchAudio,
  getAllSegments,
  getDocument,
  getDocuments,
  getSettings,
  getVoices,
  isEmptyAudio,
  patchDocument,
  putSettings,
  uploadDocument,
} from '../../src/api/client'
import type { Segment, SegmentsPage, WordTimestamp } from '../../src/api/types'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function seg(id: number, order: number): Segment {
  return {
    id,
    order,
    block_id: 1,
    type: 'paragraph',
    section_id: null,
    text: `s${id}`,
    normalized_text: `s${id}`,
    char_start: 0,
    char_end: 2,
  }
}

function page(from: number, segments: Segment[], next_from: number | null): SegmentsPage {
  return { document_id: 7, total: 3, from, limit: 500, next_from, segments }
}

function calledUrls(): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0]))
}

function fakeCtx(duration = 1.5) {
  const decodeAudioData = vi.fn(async (data: ArrayBuffer) => {
    void data
    return { duration } as unknown as AudioBuffer
  })
  return { ctx: { decodeAudioData } as unknown as AudioContext, decodeAudioData }
}

describe('client URLs', () => {
  it('getDocuments, getDocument and getVoices hit the spec §1 paths', async () => {
    fetchMock
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(json({ id: 7, sections: [] }))
      .mockResolvedValueOnce(json([{ id: 'af_heart' }]))
    await getDocuments()
    expect((await getDocument(7)).id).toBe(7)
    expect((await getVoices())[0].id).toBe('af_heart')
    expect(calledUrls()).toEqual(['/documents', '/documents/7', '/voices'])
  })

  it('audio URL carries the speed with two decimals', () => {
    expect(audioUrl(42, 'af_heart', 1.25)).toBe('/audio/42?voice=af_heart&speed=1.25')
    expect(audioUrl(42, 'af_heart', 1)).toBe('/audio/42?voice=af_heart&speed=1.00')
    expect(audioUrl(42, 'af_heart', 0.5)).toBe('/audio/42?voice=af_heart&speed=0.50')
  })
})

describe('getAllSegments', () => {
  it('follows next_from with limit=500 until null and sorts by order', async () => {
    fetchMock
      .mockResolvedValueOnce(json(page(0, [seg(12, 2), seg(10, 0)], 2)))
      .mockResolvedValueOnce(json(page(2, [seg(11, 1)], null)))
    const pages: number[] = []
    const all = await getAllSegments(7, (p) => pages.push(p.from))
    expect(calledUrls()).toEqual([
      '/documents/7/segments?from=0&limit=500',
      '/documents/7/segments?from=2&limit=500',
    ])
    expect(pages).toEqual([0, 2])
    expect(all.map((s) => s.id)).toEqual([10, 11, 12])
  })
})

describe('fetchAudio', () => {
  const TS: WordTimestamp[] = [
    { word: 'Hello', start_ms: 0, end_ms: 80, char_start: 0, char_end: 5 },
    { word: 'world', start_ms: 80, end_ms: 160, char_start: 6, char_end: 11 },
  ]

  it('parses X-Timestamps and X-Duration-Ms and decodes a copy of the bytes', async () => {
    const bytes = Uint8Array.from({ length: 64 }, (_, i) => i + 1) // more than a WAV header
    fetchMock.mockResolvedValueOnce(
      new Response(bytes, {
        status: 200,
        headers: {
          'Content-Type': 'audio/ogg; codecs=opus',
          'X-Timestamps': JSON.stringify(TS),
          'X-Duration-Ms': '1480',
        },
      }),
    )
    const { ctx, decodeAudioData } = fakeCtx(1.5)
    const clip = await fetchAudio(ctx, 42, 'af_heart', 2, new AbortController().signal)
    expect(calledUrls()).toEqual(['/audio/42?voice=af_heart&speed=2.00'])
    expect(clip.segmentId).toBe(42)
    expect(clip.voice).toBe('af_heart')
    expect(clip.speed).toBe(2)
    expect(clip.timestamps).toEqual(TS)
    expect(clip.durationMs).toBe(1480)
    expect(clip.mediaType).toBe('audio/ogg')
    expect(clip.buffer?.duration).toBe(1.5)
    expect(clip.durationSec).toBe(1.5)
    expect(clip.fetchMs).toBeGreaterThanOrEqual(0)
    expect(clip.decodeMs).toBeGreaterThanOrEqual(0)
    expect(decodeAudioData).toHaveBeenCalledTimes(1)
    const decoded = decodeAudioData.mock.calls[0][0]
    expect(Array.from(new Uint8Array(decoded))).toEqual(Array.from(bytes))
  })

  it('PLAY-5: a 44-byte header-only WAV is a zero-length clip and is not decoded', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(new Uint8Array(44), {
        status: 200,
        headers: { 'Content-Type': 'audio/wav', 'X-Timestamps': '[]' },
      }),
    )
    const { ctx, decodeAudioData } = fakeCtx(1.5)
    const clip = await fetchAudio(ctx, 32307, 'af_heart', 1)
    expect(clip.durationSec).toBe(0)
    expect(clip.durationMs).toBe(0)
    expect(clip.buffer).toBeNull()
    expect(clip.timestamps).toEqual([])
    expect(decodeAudioData).not.toHaveBeenCalled()
  })

  it('PLAY-5: X-Duration-Ms 0 is a zero-length clip even with a longer body', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(new Uint8Array(200), {
        status: 200,
        headers: { 'Content-Type': 'audio/wav', 'X-Timestamps': '[]', 'X-Duration-Ms': '0' },
      }),
    )
    const { ctx, decodeAudioData } = fakeCtx(1.5)
    const clip = await fetchAudio(ctx, 32307, 'af_heart', 1)
    expect(clip.durationSec).toBe(0)
    expect(clip.buffer).toBeNull()
    expect(decodeAudioData).not.toHaveBeenCalled()
  })

  it('PLAY-5: isEmptyAudio is true at 0 ms or <= 44 bytes and false otherwise', () => {
    expect(isEmptyAudio(0, 1000)).toBe(true)
    expect(isEmptyAudio(NaN, 44)).toBe(true)
    expect(isEmptyAudio(NaN, 0)).toBe(true)
    expect(isEmptyAudio(NaN, 45)).toBe(false)
    expect(isEmptyAudio(1480, 9000)).toBe(false)
  })

  it('a non-2xx response throws ApiError {status, url, message}', async () => {
    fetchMock.mockResolvedValueOnce(new Response('synthesis failed', { status: 502 }))
    const { ctx } = fakeCtx()
    const err = await fetchAudio(ctx, 9, 'af_heart', 1.25).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    const e = err as ApiError
    expect(e.status).toBe(502)
    expect(e.url).toBe('/audio/9?voice=af_heart&speed=1.25')
    expect(e.message).toContain('502')
    expect(e.message).toContain('synthesis failed')
  })

  it('aborts after 15 s and throws ApiError', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementationOnce(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          )
        }),
    )
    const { ctx } = fakeCtx()
    const pending = fetchAudio(ctx, 9, 'af_heart', 1).catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(TIMEOUT_MS - 1)
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    const err = await pending
    expect(TIMEOUT_MS).toBe(15_000)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(0)
    expect((err as ApiError).message).toContain('timeout')
  })

  it('the caller signal aborts the request', async () => {
    fetchMock.mockImplementationOnce(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          )
        }),
    )
    const ctrl = new AbortController()
    const { ctx } = fakeCtx()
    const pending = fetchAudio(ctx, 9, 'af_heart', 1, ctrl.signal).catch((e: unknown) => e)
    ctrl.abort()
    const err = (await pending) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('aborted')
  })
})

// M4 client functions (spec _agent/specs/m4-library-interfaces.md §1, §2). Server shapes: api/tests/test_lib_gate.py;
// an unset position is {segment_id: null, offset_ms: 0}, never null (_agent/drafts/m4-1-build-lib.md).
const SUMMARY = {
  id: 7,
  title: 'Doc',
  filename: 'doc.pdf',
  page_count: 3,
  pages_done: 3,
  status: 'ready',
  segment_count: 40,
  position: { segment_id: 12, offset_ms: 1234 },
  progress: 0.3,
  settings: { voice_id: 'af_heart', speed: 1.5 },
  last_opened_at: '2026-10-17T10:00:00Z',
}

function init(i = 0): RequestInit {
  return fetchMock.mock.calls[i][1] ?? {}
}

function headerOf(ri: RequestInit, name: string): string | null {
  return new Headers(ri.headers).get(name)
}

describe('LIB-2/LIB-3 patchDocument', () => {
  it('LIB-2 patchDocument sends PATCH JSON to /documents/{id} and returns the summary', async () => {
    fetchMock.mockResolvedValueOnce(json(SUMMARY))
    const body = { position: { segment_id: 12, offset_ms: 1234 } }
    const out = await patchDocument(7, body)
    expect(calledUrls()).toEqual(['/documents/7'])
    expect(init().method).toBe('PATCH')
    expect(headerOf(init(), 'Content-Type')).toContain('application/json')
    expect(JSON.parse(String(init().body))).toEqual(body)
    expect(init().keepalive ?? false).toBe(false)
    expect(out.position).toEqual({ segment_id: 12, offset_ms: 1234 })
    expect(out.progress).toBe(0.3)
  })

  it('LIB-2 patchDocument sets keepalive when asked (pagehide save, D26)', async () => {
    fetchMock.mockResolvedValueOnce(json(SUMMARY))
    await patchDocument(7, { position: { segment_id: 12, offset_ms: 0 } }, { keepalive: true })
    expect(init().keepalive).toBe(true)
  })

  it('LIB-3 patchDocument carries settings and opened', async () => {
    fetchMock.mockResolvedValueOnce(json(SUMMARY))
    await patchDocument(7, { settings: { voice_id: 'af_heart', speed: 1.5 }, opened: true })
    expect(JSON.parse(String(init().body))).toEqual({
      settings: { voice_id: 'af_heart', speed: 1.5 },
      opened: true,
    })
  })

  it('LIB-2 patchDocument throws ApiError on 422', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'foreign segment' }, 422))
    const err = await patchDocument(7, { position: { segment_id: 999, offset_ms: 0 } }).catch(
      (e: unknown) => e,
    )
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(422)
  })
})

describe('LIB-4 deleteDocument', () => {
  it('LIB-4 deleteDocument sends DELETE and resolves on 204', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(deleteDocument(7)).resolves.toBeUndefined()
    expect(calledUrls()).toEqual(['/documents/7'])
    expect(init().method).toBe('DELETE')
  })

  it('LIB-4 deleteDocument throws ApiError 409 while parsing', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'parsing' }, 409))
    const err = await deleteDocument(7).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(409)
  })
})

describe('LIB-3 getSettings / putSettings', () => {
  it('LIB-3 getSettings GETs /settings', async () => {
    fetchMock.mockResolvedValueOnce(json({ default_voice_id: null, default_speed: 1.25 }))
    expect(await getSettings()).toEqual({ default_voice_id: null, default_speed: 1.25 })
    expect(calledUrls()).toEqual(['/settings'])
    expect(init().method ?? 'GET').toBe('GET')
  })

  it('LIB-3 putSettings PUTs JSON and returns the stored settings', async () => {
    const s = { default_voice_id: 'af_heart', default_speed: 1.5 }
    fetchMock.mockResolvedValueOnce(json(s))
    expect(await putSettings(s)).toEqual(s)
    expect(calledUrls()).toEqual(['/settings'])
    expect(init().method).toBe('PUT')
    expect(headerOf(init(), 'Content-Type')).toContain('application/json')
    expect(JSON.parse(String(init().body))).toEqual(s)
  })
})

describe('LIB-1 uploadDocument', () => {
  it('LIB-1 uploadDocument POSTs multipart with the file under "file"', async () => {
    fetchMock.mockResolvedValueOnce(json({ id: 9, status: 'parsing' }, 202))
    const file = new File([new Uint8Array([37, 80, 68, 70])], 'paper.pdf', {
      type: 'application/pdf',
    })
    expect(await uploadDocument(file)).toEqual({ id: 9, status: 'parsing' })
    expect(calledUrls()).toEqual(['/documents'])
    expect(init().method).toBe('POST')
    const body = init().body
    expect(body).toBeInstanceOf(FormData)
    const sent = (body as FormData).get('file')
    expect(sent).toBeInstanceOf(File)
    expect((sent as File).name).toBe('paper.pdf')
    // the browser sets the multipart boundary; a hand-set Content-Type would break it
    expect(headerOf(init(), 'Content-Type')).toBeNull()
  })

  it('LIB-1 uploadDocument resolves on 200 for an already-uploaded file', async () => {
    fetchMock.mockResolvedValueOnce(json({ id: 3, status: 'ready' }, 200))
    const file = new File([new Uint8Array([1])], 'again.pdf')
    expect(await uploadDocument(file)).toEqual({ id: 3, status: 'ready' })
  })
})
