// Typed client for the HearNarro API (spec _agent/specs/m3-reader-interfaces.md §1, §4).
// Paths are relative: in dev Vite proxies them to the API (D21).

import type {
  AudioClip,
  DocumentDetail,
  DocumentPatch,
  DocumentSummary,
  GlobalSettings,
  Segment,
  SegmentsPage,
  UploadResult,
  Voice,
  WordTimestamp,
} from './types'

/** Every request is aborted after this long (spec §4). */
export const TIMEOUT_MS = 15_000
/** Page size for `getAllSegments`; the server clamps `limit` to 500. */
export const PAGE_LIMIT = 500

export class ApiError extends Error {
  readonly status: number
  readonly url: string

  constructor(status: number, url: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
  }
}

/** Format a speed for the wire: two decimals (`1.25`, `1.00`). */
export function formatSpeed(speed: number): string {
  return speed.toFixed(2)
}

export function audioUrl(segmentId: number, voice: string, speed: number): string {
  const q = new URLSearchParams({ voice, speed: formatSpeed(speed) })
  return `/audio/${segmentId}?${q.toString()}`
}

export function segmentsUrl(documentId: number, from: number, limit = PAGE_LIMIT): string {
  return `/documents/${documentId}/segments?from=${from}&limit=${limit}`
}

/**
 * fetch with a 15 s timeout (covering headers and body), chained to an optional caller signal.
 * Non-2xx and network failures throw ApiError; `read` consumes the body inside the timeout.
 */
async function request<T>(
  url: string,
  read: (res: Response) => Promise<T>,
  signal?: AbortSignal,
  init: Omit<RequestInit, 'signal'> = {},
): Promise<T> {
  const ctrl = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    ctrl.abort()
  }, TIMEOUT_MS)
  const onAbort = () => ctrl.abort()
  if (signal) {
    if (signal.aborted) ctrl.abort()
    else signal.addEventListener('abort', onAbort, { once: true })
  }
  const fail = (status: number, err: unknown): ApiError => {
    if (err instanceof ApiError) return err
    if (timedOut) return new ApiError(0, url, `timeout after ${TIMEOUT_MS} ms`)
    if (signal?.aborted) return new ApiError(0, url, 'aborted')
    return new ApiError(status, url, err instanceof Error ? err.message : String(err))
  }
  try {
    let res: Response
    try {
      res = await fetch(url, { ...init, signal: ctrl.signal })
    } catch (err) {
      throw fail(0, err)
    }
    if (!res.ok) {
      let detail = ''
      try {
        detail = await res.text()
      } catch {
        detail = ''
      }
      throw new ApiError(
        res.status,
        url,
        `${res.status} ${res.statusText}${detail ? `: ${detail}` : ''}`,
      )
    }
    try {
      return await read(res)
    } catch (err) {
      throw fail(res.status, err)
    }
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }
}

function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return request(url, async (res) => (await res.json()) as T, signal)
}

export function getDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  return getJson<DocumentSummary[]>('/documents', signal)
}

export function getDocument(id: number, signal?: AbortSignal): Promise<DocumentDetail> {
  return getJson<DocumentDetail>(`/documents/${id}`, signal)
}

/** Every segment of a document, following `next_from` with `limit=500` until null; sorted by `order`. */
export async function getAllSegments(
  id: number,
  onPage?: (page: SegmentsPage) => void,
  signal?: AbortSignal,
): Promise<Segment[]> {
  const all: Segment[] = []
  let from: number | null = 0
  while (from !== null) {
    const page: SegmentsPage = await getJson<SegmentsPage>(segmentsUrl(id, from), signal)
    all.push(...page.segments)
    onPage?.(page)
    if (page.next_from !== null && page.next_from <= from) {
      throw new ApiError(200, segmentsUrl(id, from), `next_from ${page.next_from} does not advance`)
    }
    from = page.next_from
  }
  return all.sort((a, b) => a.order - b.order)
}

function sendJson<T>(method: string, url: string, body: unknown, keepalive = false): Promise<T> {
  const init: Omit<RequestInit, 'signal'> = {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
  if (keepalive) init.keepalive = true
  return request(url, async (res) => (await res.json()) as T, undefined, init)
}

/** PATCH /documents/{id} (LIB-2 position, LIB-3 settings, `opened`); `keepalive` for the pagehide save. */
export function patchDocument(
  id: number,
  body: DocumentPatch,
  opts: { keepalive?: boolean } = {},
): Promise<DocumentSummary> {
  return sendJson<DocumentSummary>('PATCH', `/documents/${id}`, body, opts.keepalive ?? false)
}

/** DELETE /documents/{id} (LIB-4); resolves on 204, throws ApiError (409 while parsing). */
export function deleteDocument(id: number): Promise<void> {
  return request(`/documents/${id}`, async () => undefined, undefined, { method: 'DELETE' })
}

export function getSettings(signal?: AbortSignal): Promise<GlobalSettings> {
  return getJson<GlobalSettings>('/settings', signal)
}

export function putSettings(s: GlobalSettings): Promise<GlobalSettings> {
  return sendJson<GlobalSettings>('PUT', '/settings', s)
}

/** POST /documents as multipart, field "file"; no Content-Type header so the browser sets the boundary. */
export function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return request('/documents', async (res) => (await res.json()) as UploadResult, undefined, {
    method: 'POST',
    body: form,
  })
}

export function getVoices(signal?: AbortSignal): Promise<Voice[]> {
  return getJson<Voice[]>('/voices', signal)
}

/** Parse the `X-Timestamps` header; a missing header is an empty list, a malformed one throws. */
export function parseTimestamps(header: string | null, url: string): WordTimestamp[] {
  if (header === null || header === '') return []
  try {
    const v: unknown = JSON.parse(header)
    if (!Array.isArray(v)) throw new Error('not an array')
    return v as WordTimestamp[]
  } catch (err) {
    throw new ApiError(
      200,
      url,
      `bad X-Timestamps: ${err instanceof Error ? err.message : String(err)}`,
    )
  }
}

/** Bytes of a canonical WAV header with no samples; a body this size or smaller carries no audio. */
export const WAV_HEADER_BYTES = 44

/** True when a response carries no audio: X-Duration-Ms is 0, or the body is at most a WAV header. */
export function isEmptyAudio(durationMs: number, byteLength: number): boolean {
  return durationMs === 0 || byteLength <= WAV_HEADER_BYTES
}

/**
 * GET /audio/{id}, decode it, and time both steps. An empty response (see `isEmptyAudio`) is returned
 * as a zero-length clip without calling decodeAudioData, which rejects a zero-sample WAV.
 */
export async function fetchAudio(
  ctx: AudioContext,
  segmentId: number,
  voice: string,
  speed: number,
  signal?: AbortSignal,
): Promise<AudioClip> {
  const url = audioUrl(segmentId, voice, speed)
  const t0 = performance.now()
  const got = await request(
    url,
    async (res) => ({
      status: res.status,
      timestamps: parseTimestamps(res.headers.get('X-Timestamps'), url),
      durationHeader: res.headers.get('X-Duration-Ms'),
      mediaType: (res.headers.get('Content-Type') ?? '').split(';')[0].trim(),
      bytes: await res.arrayBuffer(),
    }),
    signal,
  )
  const t1 = performance.now()
  const durationMs = got.durationHeader === null ? NaN : Number(got.durationHeader)
  if (isEmptyAudio(durationMs, got.bytes.byteLength)) {
    // PLAY-5: a segment with nothing to say (e.g. a page marker) is a zero-length clip, not an error
    return {
      segmentId,
      voice,
      speed,
      buffer: null,
      durationSec: 0,
      timestamps: got.timestamps,
      durationMs: 0,
      mediaType: got.mediaType,
      fetchMs: t1 - t0,
      decodeMs: 0,
    }
  }
  let buffer: AudioBuffer
  try {
    // decodeAudioData detaches its argument; decode a copy so the fetched bytes stay intact
    buffer = await ctx.decodeAudioData(got.bytes.slice(0))
  } catch (err) {
    throw new ApiError(
      got.status,
      url,
      `decode failed: ${err instanceof Error ? err.message : String(err)}`,
    )
  }
  const t2 = performance.now()
  return {
    segmentId,
    voice,
    speed,
    buffer,
    durationSec: buffer.duration,
    timestamps: got.timestamps,
    durationMs: Number.isFinite(durationMs) ? durationMs : Math.round(buffer.duration * 1000),
    mediaType: got.mediaType,
    fetchMs: t1 - t0,
    decodeMs: t2 - t1,
  }
}
