// PLAY-1/PLAY-4: typed API client (spec §1, §4) against a mocked fetch and a fake decodeAudioData.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  TIMEOUT_MS,
  audioUrl,
  fetchAudio,
  getAllSegments,
  getDocument,
  getDocuments,
  getVoices,
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
    const bytes = new Uint8Array([1, 2, 3, 4])
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
    expect(clip.buffer.duration).toBe(1.5)
    expect(clip.fetchMs).toBeGreaterThanOrEqual(0)
    expect(clip.decodeMs).toBeGreaterThanOrEqual(0)
    expect(decodeAudioData).toHaveBeenCalledTimes(1)
    const decoded = decodeAudioData.mock.calls[0][0]
    expect(Array.from(new Uint8Array(decoded))).toEqual([1, 2, 3, 4])
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
