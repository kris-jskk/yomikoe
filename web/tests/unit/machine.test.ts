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
