// Player state machine (D10; spec _agent/specs/m3-reader-interfaces.md §5).
// Phase 1 stub: the types and signatures are fixed here; `reduce` is implemented in phase 2.

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

export const initialState: PlayerState = {
  status: 'idle',
  documentId: null,
  orderedIds: [],
  sectionStarts: [],
  current: null,
  voice: '',
  speed: 1.0,
  generation: 0,
  error: null,
  firstAudio: null,
}

export function reduce(state: PlayerState, event: PlayerEvent): PlayerState {
  void state
  void event
  throw new Error('NotImplemented: reduce')
}
