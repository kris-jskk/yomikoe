// Phase 5 stage 2 wiring seams (spec _agent/specs/m5-academic-reading.md §4d, §8 Q7): the LOAD payload
// (PLAY-10 types, PLAY-11 factor), the per-clip fetch speed (PLAY-11), the pause after a clip (SYN-8),
// the schedule settings key, the PlayerBar equation helpers and the Reader maths pieces (MATH-5).
import { describe, expect, it } from 'vitest'

import { EQUATION_FACTORS, onEquation } from '../../src/components/PlayerBar'
import { segmentPieces } from '../../src/components/Reader'
import { initialState, reduce, type PlayerState } from '../../src/player/machine'
import { tokenize } from '../../src/player/schedule'
import {
  buildLoadEvent,
  clipSpeed,
  pauseAfterSec,
  settingsKey,
} from '../../src/player/usePlayer'

const segs = [
  { id: 10, type: 'heading' },
  { id: 11, type: 'body' },
  { id: 12, type: 'equation' },
  { id: 13, type: 'equation' },
  { id: 14, type: 'list' },
]

function loaded(factor?: number): PlayerState {
  return reduce(
    initialState,
    buildLoadEvent({
      documentId: 1,
      segments: segs,
      sectionStarts: [10],
      voice: 'v',
      speed: 1.25,
      globals: factor === undefined ? null : { default_voice_id: null, default_speed: 1.25, equation_speed_factor: factor },
    }),
  )
}

describe('PLAY-10/PLAY-11 buildLoadEvent', () => {
  it('PLAY-10 LOAD carries the block type per id, aligned with orderedIds', () => {
    const e = buildLoadEvent({ documentId: 1, segments: segs, sectionStarts: [10], voice: 'v', speed: 1.25, globals: null })
    expect(e.type).toBe('LOAD')
    if (e.type !== 'LOAD') return
    expect(e.orderedIds).toEqual([10, 11, 12, 13, 14])
    expect(e.types).toEqual(['heading', 'body', 'equation', 'equation', 'list'])
  })
  it('PLAY-11 LOAD carries equation_speed_factor from GET /settings, clamped to the grid', () => {
    expect(loaded(0.6).blockSpeed).toEqual({ equation: 0.6 })
    expect(loaded(0.33).blockSpeed).toEqual({ equation: 0.5 })
  })
  it('PLAY-11 LOAD falls back to the 0.8 default without the setting', () => {
    expect(loaded().blockSpeed).toEqual({ equation: 0.8 })
  })
})

describe('PLAY-11 clipSpeed', () => {
  it('PLAY-11 an equation clip is requested at speed x factor on the 0.05 grid', () => {
    expect(clipSpeed(loaded(), 12)).toBe(1.0)
    expect(clipSpeed(loaded(0.6), 13)).toBe(0.75)
  })
  it('PLAY-11 every other type is requested at the document speed', () => {
    for (const id of [10, 11, 14]) expect(clipSpeed(loaded(0.6), id)).toBe(1.25)
  })
  it('PLAY-11 an id outside the document plays at the document speed', () => {
    expect(clipSpeed(loaded(), 999)).toBe(1.25)
  })
})

describe('SYN-8 pauseAfterSec', () => {
  it('SYN-8 heading, list and equation clips are followed by their pause, body by none', () => {
    const s = loaded()
    expect(pauseAfterSec(s, 10)).toBeCloseTo(0.6)
    expect(pauseAfterSec(s, 11)).toBe(0)
    expect(pauseAfterSec(s, 12)).toBeCloseTo(0.4)
    expect(pauseAfterSec(s, 14)).toBeCloseTo(0.25)
  })
})

describe('PLAY-11 settingsKey', () => {
  it('PLAY-11 a factor change changes the key, like a speed change', () => {
    const a = settingsKey('v', 1.25, { equation: 0.8 })
    expect(settingsKey('v', 1.25, { equation: 0.8 })).toBe(a)
    expect(settingsKey('v', 1.25, { equation: 0.7 })).not.toBe(a)
    expect(settingsKey('v', 1.5, { equation: 0.8 })).not.toBe(a)
  })
})

describe('PLAY-10 onEquation and the PLAY-11 select steps', () => {
  it('PLAY-10 true only while the current segment is an equation', () => {
    const s = loaded()
    expect(onEquation(s)).toBe(false) // current is the first id (heading)
    expect(onEquation({ ...s, current: { segmentId: 12, offsetMs: 0 } })).toBe(true)
    expect(onEquation({ ...s, current: { segmentId: 14, offsetMs: 0 } })).toBe(false)
    expect(onEquation(initialState)).toBe(false)
  })
  it('PLAY-11 the select offers the 0.05 grid from 0.5 to 1.0', () => {
    expect(EQUATION_FACTORS).toEqual([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0])
  })
})

describe('MATH-5 segmentPieces', () => {
  it('MATH-5 tokens inside a maths range are one piece, the rest one piece per token', () => {
    const text = 'Let x = a + b hold.'
    const toks = tokenize(text)
    const pieces = segmentPieces(text, toks, [{ start: 4, end: 13, display: false }])
    expect(pieces).toEqual([
      { kind: 'w', i: 0 },
      { kind: 'math', from: 1, to: 5, display: false, text: 'x = a + b' },
      { kind: 'w', i: 6 },
    ])
  })
  it('MATH-5 a display range covering the whole segment is one boxed piece', () => {
    const text = 'p(y | x) = sum'
    const toks = tokenize(text)
    expect(segmentPieces(text, toks, [{ start: 0, end: text.length, display: true }])).toEqual([
      { kind: 'math', from: 0, to: toks.length - 1, display: true, text },
    ])
  })
  it('MATH-5 no ranges keeps one word piece per token (word highlight unchanged)', () => {
    const text = 'plain words here'
    expect(segmentPieces(text, tokenize(text), undefined)).toEqual([
      { kind: 'w', i: 0 },
      { kind: 'w', i: 1 },
      { kind: 'w', i: 2 },
    ])
  })
})
