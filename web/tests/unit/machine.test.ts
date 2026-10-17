// PLAY-1..PLAY-5: player reducer, one `it` per transition row of spec §5 (named `<EVENT> from <state>`).
import { describe, expect, it } from 'vitest'

import {
  initialState,
  reduce,
  type PlayerEvent,
  type PlayerState,
  type PlayerStatus,
} from '../../src/player/machine'

// Ten segments in reading order; three sections starting at 101, 104 and 108.
const IDS = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
const SECTION_STARTS = [101, 104, 108]

function st(status: PlayerStatus, over: Partial<PlayerState> = {}): PlayerState {
  return {
    ...initialState,
    status,
    documentId: 7,
    orderedIds: IDS,
    sectionStarts: SECTION_STARTS,
    current: { segmentId: 105, offsetMs: 2300 },
    voice: 'af_heart',
    speed: 1.0,
    generation: 5,
    error: null,
    firstAudio: { requestedAt: 1000, startedAt: null },
    ...over,
  }
}

const load: PlayerEvent = {
  type: 'LOAD',
  documentId: 7,
  orderedIds: IDS,
  sectionStarts: SECTION_STARTS,
  voice: 'af_heart',
  speed: 1.25,
}

describe('PLAY-1..PLAY-5 player reducer', () => {
  it('LOAD from idle', () => {
    const s = reduce(initialState, load)
    expect(s.status).toBe('idle')
    expect(s.documentId).toBe(7)
    expect(s.orderedIds).toEqual(IDS)
    expect(s.sectionStarts).toEqual(SECTION_STARTS)
    expect(s.voice).toBe('af_heart')
    expect(s.speed).toBe(1.25)
    expect(s.current).toEqual({ segmentId: 101, offsetMs: 0 })
  })

  it('LOAD from error', () => {
    const s = reduce(st('error', { error: 'boom', documentId: 3, orderedIds: [1, 2] }), {
      ...load,
      position: { segmentId: 106, offsetMs: 1200 },
    })
    expect(s.status).toBe('idle')
    expect(s.documentId).toBe(7)
    expect(s.orderedIds).toEqual(IDS)
    expect(s.current).toEqual({ segmentId: 106, offsetMs: 1200 })
  })

  it('PLAY from idle', () => {
    const s = reduce(st('idle', { current: { segmentId: 103, offsetMs: 0 }, firstAudio: null }), {
      type: 'PLAY',
      at: 5000,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 103, offsetMs: 0 })
    expect(s.firstAudio).toEqual({ requestedAt: 5000, startedAt: null })
  })

  it('PLAY from paused', () => {
    const s = reduce(st('paused'), { type: 'PLAY', at: 6000, segmentId: 106, offsetMs: 300 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 106, offsetMs: 300 })
    expect(s.firstAudio).toEqual({ requestedAt: 6000, startedAt: null })
  })

  it('PLAY from error', () => {
    const s = reduce(st('error', { error: 'boom' }), { type: 'PLAY', at: 7000 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
    expect(s.firstAudio).toEqual({ requestedAt: 7000, startedAt: null })
  })

  it('AUDIO_READY from loading', () => {
    const s = reduce(st('loading'), { type: 'AUDIO_READY', generation: 5, at: 1830 })
    expect(s.status).toBe('playing')
    expect(s.generation).toBe(5)
    expect(s.firstAudio).toEqual({ requestedAt: 1000, startedAt: 1830 })
  })

  it('PAUSE from playing', () => {
    const before = st('playing')
    const s = reduce(before, { type: 'PAUSE' })
    expect(s.status).toBe('paused')
    expect(s.current).toEqual(before.current)
    expect(s.generation).toBe(5)
  })

  it('RESUME from paused', () => {
    const before = st('paused')
    const s = reduce(before, { type: 'RESUME' })
    expect(s.status).toBe('playing')
    expect(s.current).toEqual(before.current)
    expect(s.generation).toBe(5)
  })

  it('SEEK from playing', () => {
    const s = reduce(st('playing'), { type: 'SEEK', segmentId: 107 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 107, offsetMs: 0 })
  })

  it('SEEK from paused', () => {
    const s = reduce(st('paused'), { type: 'SEEK', segmentId: 107, offsetMs: 450 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 107, offsetMs: 450 })
  })

  it('SEEK from loading', () => {
    const s = reduce(st('loading'), { type: 'SEEK', segmentId: 102 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 102, offsetMs: 0 })
  })

  it('SKIP from playing', () => {
    const s = reduce(st('playing', { current: { segmentId: 103, offsetMs: 900 } }), {
      type: 'SKIP',
      by: 1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 104, offsetMs: 0 })
    // clamped at the last segment
    const last = reduce(st('playing', { current: { segmentId: 110, offsetMs: 900 } }), {
      type: 'SKIP',
      by: 1,
    })
    expect(last.current).toEqual({ segmentId: 110, offsetMs: 0 })
  })

  it('SKIP from paused', () => {
    const s = reduce(st('paused', { current: { segmentId: 103, offsetMs: 900 } }), {
      type: 'SKIP',
      by: -1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 102, offsetMs: 0 })
    // clamped at the first segment
    const first = reduce(st('paused', { current: { segmentId: 101, offsetMs: 900 } }), {
      type: 'SKIP',
      by: -1,
    })
    expect(first.current).toEqual({ segmentId: 101, offsetMs: 0 })
  })

  it('SKIP_SECTION from playing', () => {
    const s = reduce(st('playing', { current: { segmentId: 105, offsetMs: 900 } }), {
      type: 'SKIP_SECTION',
      by: 1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 108, offsetMs: 0 })
  })

  it('SKIP_SECTION from paused', () => {
    const s = reduce(st('paused', { current: { segmentId: 104, offsetMs: 0 } }), {
      type: 'SKIP_SECTION',
      by: -1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 101, offsetMs: 0 })
    // clamped before the first section
    const first = reduce(st('paused', { current: { segmentId: 102, offsetMs: 0 } }), {
      type: 'SKIP_SECTION',
      by: -1,
    })
    expect(first.current).toEqual({ segmentId: 101, offsetMs: 0 })
  })

  it('SKIP_SECTION +1 with no later section is a no-op (same object)', () => {
    const before = st('playing', { current: { segmentId: 109, offsetMs: 400 } })
    expect(reduce(before, { type: 'SKIP_SECTION', by: 1 })).toBe(before)
  })

  it('SKIP_SECTION -1 mid-section goes to the current section start', () => {
    const s = reduce(st('playing', { current: { segmentId: 106, offsetMs: 400 } }), {
      type: 'SKIP_SECTION',
      by: -1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 104, offsetMs: 0 })
  })

  it('SKIP_SECTION -1 at a section start goes to the previous section start', () => {
    const s = reduce(st('playing', { current: { segmentId: 108, offsetMs: 0 } }), {
      type: 'SKIP_SECTION',
      by: -1,
    })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 104, offsetMs: 0 })
  })

  it('SET_VOICE from playing', () => {
    const s = reduce(st('playing'), { type: 'SET_VOICE', voice: 'bm_george' })
    expect(s.status).toBe('loading')
    expect(s.voice).toBe('bm_george')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 0 })
  })

  it('SET_VOICE from paused', () => {
    const s = reduce(st('paused'), { type: 'SET_VOICE', voice: 'bm_george' })
    expect(s.status).toBe('paused')
    expect(s.voice).toBe('bm_george')
    expect(s.generation).toBe(5)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('SET_VOICE from idle', () => {
    const s = reduce(st('idle'), { type: 'SET_VOICE', voice: 'bm_george' })
    expect(s.status).toBe('idle')
    expect(s.voice).toBe('bm_george')
    expect(s.generation).toBe(5)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('SET_SPEED from playing', () => {
    const s = reduce(st('playing'), { type: 'SET_SPEED', speed: 2.0 })
    expect(s.status).toBe('loading')
    expect(s.speed).toBe(2.0)
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 0 })
  })

  it('SET_SPEED from paused', () => {
    const s = reduce(st('paused'), { type: 'SET_SPEED', speed: 2.0 })
    expect(s.status).toBe('paused')
    expect(s.speed).toBe(2.0)
    expect(s.generation).toBe(5)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('SET_SPEED from idle', () => {
    const s = reduce(st('idle'), { type: 'SET_SPEED', speed: 0.75 })
    expect(s.status).toBe('idle')
    expect(s.speed).toBe(0.75)
    expect(s.generation).toBe(5)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('SEGMENT_STARTED from playing', () => {
    const s = reduce(st('playing'), { type: 'SEGMENT_STARTED', segmentId: 106, generation: 5 })
    expect(s.status).toBe('playing')
    expect(s.current).toEqual({ segmentId: 106, offsetMs: 0 })
  })

  it('POSITION from playing', () => {
    const s = reduce(st('playing'), { type: 'POSITION', segmentId: 105, offsetMs: 1750 })
    expect(s.status).toBe('playing')
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 1750 })
  })

  it('BUFFERING from playing', () => {
    const s = reduce(st('playing'), { type: 'BUFFERING', generation: 5 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(5)
  })

  it('BUFFERING keeps generation', () => {
    const before = st('playing')
    const s = reduce(before, { type: 'BUFFERING', generation: 5 })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(before.generation)
    expect(s.current).toEqual(before.current)
  })

  it('ENDED from playing', () => {
    const s = reduce(st('playing', { current: { segmentId: 110, offsetMs: 2900 } }), {
      type: 'ENDED',
      offsetMs: 3120,
    })
    expect(s.status).toBe('paused')
    expect(s.current).toEqual({ segmentId: 110, offsetMs: 3120 })
  })

  it('FETCH_FAILED from loading', () => {
    const s = reduce(st('loading'), {
      type: 'FETCH_FAILED',
      message: '502 synthesis failed',
      generation: 5,
    })
    expect(s.status).toBe('error')
    expect(s.error).toBe('502 synthesis failed')
  })

  it('FETCH_FAILED from playing', () => {
    const s = reduce(st('playing'), { type: 'FETCH_FAILED', message: 'timeout', generation: 5 })
    expect(s.status).toBe('error')
    expect(s.error).toBe('timeout')
  })

  it('RETRY from error', () => {
    const s = reduce(st('error', { error: 'timeout' }), { type: 'RETRY' })
    expect(s.status).toBe('loading')
    expect(s.generation).toBe(6)
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('DISMISS from error', () => {
    const s = reduce(st('error', { error: 'timeout' }), { type: 'DISMISS' })
    expect(s.status).toBe('idle')
  })

  it('stale generation is ignored', () => {
    const loading = st('loading')
    expect(reduce(loading, { type: 'AUDIO_READY', generation: 4, at: 1830 })).toEqual(loading)
    expect(reduce(loading, { type: 'FETCH_FAILED', message: 'old', generation: 4 })).toEqual(
      loading,
    )
    const playing = st('playing')
    expect(reduce(playing, { type: 'SEGMENT_STARTED', segmentId: 106, generation: 4 })).toEqual(
      playing,
    )
    expect(reduce(playing, { type: 'BUFFERING', generation: 4 })).toEqual(playing)
    expect(reduce(playing, { type: 'FETCH_FAILED', message: 'old', generation: 4 })).toEqual(
      playing,
    )
  })

  it('unknown event is identity', () => {
    const idle = st('idle')
    expect(reduce(idle, { type: 'PAUSE' })).toBe(idle)
    expect(reduce(idle, { type: 'RETRY' })).toBe(idle)
    const playing = st('playing')
    expect(reduce(playing, { type: 'RESUME' })).toBe(playing)
    expect(reduce(playing, { type: 'AUDIO_READY', generation: 5, at: 1 })).toBe(playing)
    expect(reduce(playing, load)).toBe(playing)
    const loading = st('loading')
    expect(reduce(loading, { type: 'DISMISS' })).toBe(loading)
    expect(reduce(loading, { type: 'POSITION', segmentId: 105, offsetMs: 1 })).toBe(loading)
    const paused = st('paused')
    expect(reduce(paused, { type: 'ENDED', offsetMs: 0 })).toBe(paused)
    const error = st('error', { error: 'x' })
    expect(reduce(error, { type: 'PAUSE' })).toBe(error)
    const bogus = { type: 'NOT_AN_EVENT' } as unknown as PlayerEvent
    expect(reduce(playing, bogus)).toBe(playing)
  })
})

// M4 events (spec _agent/specs/m4-library-interfaces.md §2): SET_SKIP (PLAY-8), RESTORE_POSITION and
// TICK_SAVE (LIB-2), settings while loading (LIB-3, M3 deviation 6). The hook computes skippedIds with
// player/skip.ts; the reducer only stores and honours them.
const SKIP_ALL = { footnotes: true, captions: true, references: true }

describe('PLAY-8 SET_SKIP', () => {
  it('PLAY-8 SET_SKIP stores the toggles and the skipped ids', () => {
    const s = reduce(st('paused'), { type: 'SET_SKIP', skip: SKIP_ALL, skippedIds: [102, 103] })
    expect(s.skip).toEqual(SKIP_ALL)
    expect([...s.skippedIds]).toEqual([102, 103])
    expect(s.current).toEqual({ segmentId: 105, offsetMs: 2300 })
  })

  it('PLAY-8 SET_SKIP from idle moves a newly skipped current segment to the next unskipped', () => {
    const s = reduce(st('idle'), { type: 'SET_SKIP', skip: SKIP_ALL, skippedIds: [105, 106] })
    expect(s.status).toBe('idle')
    expect(s.current).toEqual({ segmentId: 107, offsetMs: 0 })
  })

  it('PLAY-8 SET_SKIP from playing rebuilds at the next unskipped segment', () => {
    const s = reduce(st('playing'), { type: 'SET_SKIP', skip: SKIP_ALL, skippedIds: [105, 106] })
    expect(s.status).toBe('loading')
    expect(s.current).toEqual({ segmentId: 107, offsetMs: 0 })
    expect(s.generation).toBe(6)
  })

  it('PLAY-8 SKIP jumps over skipped segments', () => {
    const skipped = reduce(st('paused', { current: { segmentId: 104, offsetMs: 0 } }), {
      type: 'SET_SKIP',
      skip: SKIP_ALL,
      skippedIds: [105, 106],
    })
    expect(reduce(skipped, { type: 'SKIP', by: 1 }).current).toEqual({
      segmentId: 107,
      offsetMs: 0,
    })
    const back = reduce(
      { ...skipped, current: { segmentId: 107, offsetMs: 0 } },
      { type: 'SKIP', by: -1 },
    )
    expect(back.current).toEqual({ segmentId: 104, offsetMs: 0 })
  })

  it('PLAY-8 SEEK onto a skipped segment lands on the next unskipped', () => {
    const skipped = reduce(st('paused'), {
      type: 'SET_SKIP',
      skip: SKIP_ALL,
      skippedIds: [108, 109],
    })
    expect(reduce(skipped, { type: 'SEEK', segmentId: 108 }).current).toEqual({
      segmentId: 110,
      offsetMs: 0,
    })
  })
})

describe('LIB-2 RESTORE_POSITION', () => {
  it('LIB-2 RESTORE_POSITION from idle sets current and offset before the first PLAY', () => {
    const loaded = reduce(initialState, load)
    const s = reduce(loaded, { type: 'RESTORE_POSITION', segmentId: 106, offsetMs: 1500 })
    expect(s.status).toBe('idle')
    expect(s.current).toEqual({ segmentId: 106, offsetMs: 1500 })
    const playing = reduce(s, { type: 'PLAY', at: 1 })
    expect(playing.current).toEqual({ segmentId: 106, offsetMs: 1500 })
  })

  it('LIB-2 RESTORE_POSITION is ignored once playback has started', () => {
    const s = st('playing')
    expect(reduce(s, { type: 'RESTORE_POSITION', segmentId: 101, offsetMs: 0 })).toBe(s)
  })

  it('LIB-2 RESTORE_POSITION for a segment not in the document is ignored', () => {
    const s = st('idle')
    expect(reduce(s, { type: 'RESTORE_POSITION', segmentId: 999, offsetMs: 0 })).toBe(s)
  })
})

describe('LIB-2 TICK_SAVE', () => {
  it('LIB-2 TICK_SAVE from playing yields the {segment_id, offset_ms} payload', () => {
    const s = reduce(st('playing'), { type: 'TICK_SAVE' })
    expect(s.pendingSave).toEqual({ segment_id: 105, offset_ms: 2300 })
  })

  it.each(['idle', 'loading', 'paused', 'error'] as const)(
    'LIB-2 TICK_SAVE from %s yields nothing',
    (status) => {
      const s = st(status)
      const out = reduce(s, { type: 'TICK_SAVE' })
      expect(out).toBe(s)
      expect(out.pendingSave ?? null).toBeNull()
    },
  )

  it('LIB-2 initial state has no pending save', () => {
    expect(initialState.pendingSave).toBeNull()
  })
})

describe('LIB-3 settings while loading (M3 deviation 6)', () => {
  it('LIB-3 SET_SPEED from loading is applied when the load finishes', () => {
    const s1 = reduce(st('loading'), { type: 'SET_SPEED', speed: 1.5 })
    const s2 = reduce(s1, { type: 'AUDIO_READY', generation: s1.generation, at: 2000 })
    expect(s2.speed).toBe(1.5)
  })

  it('LIB-3 SET_VOICE from loading is applied when the load finishes', () => {
    const s1 = reduce(st('loading'), { type: 'SET_VOICE', voice: 'am_adam' })
    const s2 = reduce(s1, { type: 'AUDIO_READY', generation: s1.generation, at: 2000 })
    expect(s2.voice).toBe('am_adam')
  })
})
