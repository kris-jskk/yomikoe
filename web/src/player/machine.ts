// Player state machine (D10; spec _agent/specs/m3-reader-interfaces.md §5).
// Pure and totally defined: an event not listed for the current state returns the same object.

export type PlayerStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'error'

export interface PlayerContext {
  documentId: number | null
  /** Segment ids in reading order (from getAllSegments). */
  orderedIds: number[]
  /** first_segment_id of every section, in reading order (needed by SKIP_SECTION). */
  sectionStarts: number[]
  /** The segment the listener is on, and where in it. */
  current: { segmentId: number; offsetMs: number } | null
  voice: string
  /** A 0.05 multiple in [0.5, 3.0]. */
  speed: number
  /** Bumped on every schedule rebuild; stale audio events are ignored. */
  generation: number
  error: string | null
  /** D19 instrumentation. */
  firstAudio: { requestedAt: number; startedAt: number | null } | null
}

export type PlayerState = { status: PlayerStatus } & PlayerContext

export type PlayerEvent =
  | {
      type: 'LOAD'
      documentId: number
      orderedIds: number[]
      sectionStarts: number[]
      voice: string
      speed: number
      position?: { segmentId: number; offsetMs: number }
    }
  | { type: 'PLAY'; at: number; segmentId?: number; offsetMs?: number }
  | { type: 'AUDIO_READY'; generation: number; at: number }
  | { type: 'PAUSE' }
  | { type: 'RESUME' }
  | { type: 'SEEK'; segmentId: number; offsetMs?: number }
  | { type: 'SKIP'; by: 1 | -1 }
  | { type: 'SKIP_SECTION'; by: 1 | -1 }
  | { type: 'SET_VOICE'; voice: string }
  | { type: 'SET_SPEED'; speed: number }
  | { type: 'SEGMENT_STARTED'; segmentId: number; generation: number }
  | { type: 'POSITION'; segmentId: number; offsetMs: number }
  | { type: 'BUFFERING'; generation: number }
  | { type: 'ENDED'; offsetMs: number }
  | { type: 'FETCH_FAILED'; message: string; generation: number }
  | { type: 'RETRY' }
  | { type: 'DISMISS' }

/** Global default speed for a document with no saved setting (LIB-3 global default is M4; user chose 1.25 on 2026-10-17). */
export const DEFAULT_SPEED = 1.25

export const initialState: PlayerState = {
  status: 'idle',
  documentId: null,
  orderedIds: [],
  sectionStarts: [],
  current: null,
  voice: '',
  speed: DEFAULT_SPEED,
  generation: 0,
  error: null,
  firstAudio: null,
}

/** Index of `id` in `orderedIds`, or -1. */
export function indexOf(orderedIds: number[], id: number): number {
  return orderedIds.indexOf(id)
}

function load(state: PlayerState, s: PlayerStatus, current: PlayerState['current']): PlayerState {
  return { ...state, status: s, current, generation: state.generation + 1 }
}

/** SKIP_SECTION target per spec §5, or null for a no-op. */
function sectionTarget(ctx: PlayerContext, by: 1 | -1): number | null {
  if (ctx.current === null) return null
  const ids = ctx.orderedIds
  const cur = indexOf(ids, ctx.current.segmentId)
  if (cur < 0) return null
  // section starts with their reading-order index, skipping any id not in orderedIds
  const starts = ctx.sectionStarts
    .map((id) => ({ id, i: indexOf(ids, id) }))
    .filter((x) => x.i >= 0)
    .sort((a, b) => a.i - b.i)
  if (by === 1) {
    const next = starts.find((x) => x.i > cur)
    return next ? next.id : null
  }
  // the section containing current: the last start at or before it
  let k = -1
  for (let j = 0; j < starts.length; j++) if (starts[j].i <= cur) k = j
  if (k < 0) return null
  if (starts[k].i !== cur) return starts[k].id
  return k > 0 ? starts[k - 1].id : null
}

export function reduce(state: PlayerState, event: PlayerEvent): PlayerState {
  const st = state.status
  switch (event.type) {
    case 'LOAD': {
      if (st !== 'idle' && st !== 'error') return state
      const first = event.orderedIds.length > 0 ? event.orderedIds[0] : null
      const current = event.position
        ? { segmentId: event.position.segmentId, offsetMs: event.position.offsetMs }
        : first !== null
          ? { segmentId: first, offsetMs: 0 }
          : null
      return {
        ...state,
        status: 'idle',
        documentId: event.documentId,
        orderedIds: event.orderedIds,
        sectionStarts: event.sectionStarts,
        voice: event.voice,
        speed: event.speed,
        current,
        error: null,
        firstAudio: null,
      }
    }
    case 'PLAY': {
      if (st !== 'idle' && st !== 'paused' && st !== 'error') return state
      const current =
        event.segmentId !== undefined
          ? { segmentId: event.segmentId, offsetMs: event.offsetMs ?? 0 }
          : state.current
      if (current === null) return state
      return {
        ...load(state, 'loading', current),
        error: null,
        firstAudio: { requestedAt: event.at, startedAt: null },
      }
    }
    case 'AUDIO_READY': {
      if (st !== 'loading' || event.generation !== state.generation) return state
      const fa = state.firstAudio
      return {
        ...state,
        status: 'playing',
        firstAudio: fa && fa.startedAt === null ? { ...fa, startedAt: event.at } : fa,
      }
    }
    case 'PAUSE':
      return st === 'playing' ? { ...state, status: 'paused' } : state
    case 'RESUME':
      return st === 'paused' ? { ...state, status: 'playing' } : state
    case 'SEEK':
      if (st !== 'playing' && st !== 'paused' && st !== 'loading') return state
      return load(state, 'loading', { segmentId: event.segmentId, offsetMs: event.offsetMs ?? 0 })
    case 'SKIP': {
      if ((st !== 'playing' && st !== 'paused') || state.current === null) return state
      const ids = state.orderedIds
      const cur = indexOf(ids, state.current.segmentId)
      if (cur < 0) return state
      const next = Math.min(ids.length - 1, Math.max(0, cur + event.by))
      return load(state, 'loading', { segmentId: ids[next], offsetMs: 0 })
    }
    case 'SKIP_SECTION': {
      if (st !== 'playing' && st !== 'paused') return state
      const target = sectionTarget(state, event.by)
      if (target === null) return state
      return load(state, 'loading', { segmentId: target, offsetMs: 0 })
    }
    case 'SET_VOICE':
    case 'SET_SPEED': {
      const patch = event.type === 'SET_VOICE' ? { voice: event.voice } : { speed: event.speed }
      if (st === 'playing') {
        const current = state.current ? { segmentId: state.current.segmentId, offsetMs: 0 } : null
        return { ...load(state, 'loading', current), ...patch }
      }
      if (st === 'paused' || st === 'idle') return { ...state, ...patch }
      return state
    }
    case 'SEGMENT_STARTED':
      if (st !== 'playing' || event.generation !== state.generation) return state
      return { ...state, current: { segmentId: event.segmentId, offsetMs: 0 } }
    case 'POSITION':
      if (st !== 'playing') return state
      return { ...state, current: { segmentId: event.segmentId, offsetMs: event.offsetMs } }
    case 'BUFFERING':
      if (st !== 'playing' || event.generation !== state.generation) return state
      return { ...state, status: 'loading' }
    case 'ENDED': {
      if (st !== 'playing') return state
      const ids = state.orderedIds
      const last = ids.length > 0 ? ids[ids.length - 1] : (state.current?.segmentId ?? null)
      return {
        ...state,
        status: 'paused',
        current: last === null ? state.current : { segmentId: last, offsetMs: event.offsetMs },
      }
    }
    case 'FETCH_FAILED':
      if ((st !== 'loading' && st !== 'playing') || event.generation !== state.generation)
        return state
      return { ...state, status: 'error', error: event.message }
    case 'RETRY':
      if (st !== 'error' || state.current === null) return state
      return { ...load(state, 'loading', state.current), error: null }
    case 'DISMISS':
      return st === 'error' ? { ...state, status: 'idle', error: null } : state
    default:
      return state
  }
}
