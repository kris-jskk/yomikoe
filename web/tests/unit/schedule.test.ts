// PLAY-2/PLAY-3/PLAY-5: pure timing helpers (spec §6, §8 "Unit").
import { describe, expect, it } from 'vitest'

import type { WordTimestamp } from '../../src/api/types'
import {
  chainStart,
  findActiveWord,
  locate,
  mapTimestampsToTokens,
  nextPlayable,
  onFetchFailure,
  tokenize,
  type MappedTimestamp,
  type ScheduleEntryView,
  type Token,
} from '../../src/player/schedule'

// "The quick brown fox jumps." whitespace tokens, spans hard-coded (not derived from tokenize).
const TEXT = 'The quick brown fox jumps.'
const TOKENS: Token[] = [
  { token: 'The', charStart: 0, charEnd: 3 },
  { token: 'quick', charStart: 4, charEnd: 9 },
  { token: 'brown', charStart: 10, charEnd: 15 },
  { token: 'fox', charStart: 16, charEnd: 19 },
  { token: 'jumps.', charStart: 20, charEnd: 26 },
]

// FakeBackend shape at speed 1.0: 80 ms per word, back to back, char spans equal to the token spans.
const FAKE_TS: WordTimestamp[] = TOKENS.map((t, i) => ({
  word: t.token,
  start_ms: i * 80,
  end_ms: (i + 1) * 80,
  char_start: t.charStart,
  char_end: t.charEnd,
}))

describe('tokenize', () => {
  it('offsets round-trip into the text', () => {
    expect(tokenize(TEXT)).toEqual(TOKENS)
  })

  it('offsets round-trip with leading, repeated and mixed whitespace', () => {
    const text = '  Hello,\tworld \n again  '
    const tokens = tokenize(text)
    expect(tokens.map((t) => t.token)).toEqual(['Hello,', 'world', 'again'])
    for (const t of tokens) {
      expect(text.slice(t.charStart, t.charEnd)).toBe(t.token)
    }
    expect(tokens[0].charStart).toBe(2)
  })

  it('empty and whitespace-only text give no tokens', () => {
    expect(tokenize('')).toEqual([])
    expect(tokenize('   \n ')).toEqual([])
  })
})

describe('mapTimestampsToTokens', () => {
  it('maps FakeBackend-shaped timestamps one to one', () => {
    expect(mapTimestampsToTokens(TOKENS, FAKE_TS)).toEqual([
      { start_ms: 0, end_ms: 80, tokenIndex: 0 },
      { start_ms: 80, end_ms: 160, tokenIndex: 1 },
      { start_ms: 160, end_ms: 240, tokenIndex: 2 },
      { start_ms: 240, end_ms: 320, tokenIndex: 3 },
      { start_ms: 320, end_ms: 400, tokenIndex: 4 },
    ])
  })

  it('a timestamp spanning two tokens goes to the first overlapping token', () => {
    const ts: WordTimestamp[] = [
      { word: 'The', start_ms: 0, end_ms: 80, char_start: 0, char_end: 3 },
      // "quick brown" spoken as one unit: overlaps tokens 1 and 2
      { word: 'quick brown', start_ms: 80, end_ms: 240, char_start: 4, char_end: 15 },
      { word: 'fox', start_ms: 240, end_ms: 320, char_start: 16, char_end: 19 },
    ]
    expect(mapTimestampsToTokens(TOKENS, ts)).toEqual([
      { start_ms: 0, end_ms: 80, tokenIndex: 0 },
      { start_ms: 80, end_ms: 240, tokenIndex: 1 },
      { start_ms: 240, end_ms: 320, tokenIndex: 3 },
    ])
  })

  it('a timestamp overlapping no token is dropped', () => {
    const ts: WordTimestamp[] = [
      { word: 'The', start_ms: 0, end_ms: 80, char_start: 0, char_end: 3 },
      // covers only the space between "The" and "quick"
      { word: '', start_ms: 80, end_ms: 90, char_start: 3, char_end: 4 },
      { word: 'quick', start_ms: 90, end_ms: 170, char_start: 4, char_end: 9 },
    ]
    expect(mapTimestampsToTokens(TOKENS, ts)).toEqual([
      { start_ms: 0, end_ms: 80, tokenIndex: 0 },
      { start_ms: 90, end_ms: 170, tokenIndex: 1 },
    ])
  })
})

describe('locate', () => {
  // windows [0, 2.5), [2.5, 5.5), gap [5.5, 6.0), [6.0, 7.0), then nothing after 7.0
  const ENTRIES: ScheduleEntryView[] = [
    { segmentId: 11, startAt: 0, durationSec: 2.5 },
    { segmentId: 12, startAt: 2.5, durationSec: 3.0 },
    { segmentId: 13, startAt: 6.0, durationSec: 1.0 },
  ]

  it('finds the entry whose window contains currentTime', () => {
    const a = locate(ENTRIES, 1.0)
    expect(a?.segmentId).toBe(11)
    expect(a?.elapsedMs).toBeCloseTo(1000, 6)
    const b = locate(ENTRIES, 4.0)
    expect(b?.segmentId).toBe(12)
    expect(b?.elapsedMs).toBeCloseTo(1500, 6)
    const c = locate(ENTRIES, 6.5)
    expect(c?.segmentId).toBe(13)
    expect(c?.elapsedMs).toBeCloseTo(500, 6)
  })

  it('a boundary belongs to the entry that starts there', () => {
    const b = locate(ENTRIES, 2.5)
    expect(b?.segmentId).toBe(12)
    expect(b?.elapsedMs).toBeCloseTo(0, 6)
  })

  it('returns null in a gap between entries and in the gap after the last', () => {
    expect(locate(ENTRIES, 5.75)).toBeNull()
    expect(locate(ENTRIES, 7.25)).toBeNull()
  })

  it('returns null before the first entry and for no entries', () => {
    expect(locate(ENTRIES, -0.1)).toBeNull()
    expect(locate([], 1.0)).toBeNull()
  })
})

describe('findActiveWord', () => {
  // three words with gaps: [100, 180), [200, 280), [300, 380); token indices 0, 2, 3 (token 1 unmapped)
  const MAPPED: MappedTimestamp[] = [
    { start_ms: 100, end_ms: 180, tokenIndex: 0 },
    { start_ms: 200, end_ms: 280, tokenIndex: 2 },
    { start_ms: 300, end_ms: 380, tokenIndex: 3 },
  ]

  it('before the first word is null', () => {
    expect(findActiveWord(MAPPED, 0)).toBeNull()
    expect(findActiveWord(MAPPED, 99.9)).toBeNull()
  })

  it('at and inside a word returns its token index', () => {
    expect(findActiveWord(MAPPED, 100)).toBe(0)
    expect(findActiveWord(MAPPED, 150)).toBe(0)
    expect(findActiveWord(MAPPED, 200)).toBe(2)
    expect(findActiveWord(MAPPED, 300)).toBe(3)
  })

  it('between words the previous token stays active', () => {
    expect(findActiveWord(MAPPED, 190)).toBe(0)
    expect(findActiveWord(MAPPED, 290)).toBe(2)
  })

  it('after the last word the last token stays active', () => {
    expect(findActiveWord(MAPPED, 380)).toBe(3)
    expect(findActiveWord(MAPPED, 10_000)).toBe(3)
  })

  it('on FakeBackend-shaped timestamps (back to back) follows 80 ms per word', () => {
    const mapped = FAKE_TS.map((t, i) => ({
      start_ms: t.start_ms,
      end_ms: t.end_ms,
      tokenIndex: i,
    }))
    expect(findActiveWord(mapped, 0)).toBe(0)
    expect(findActiveWord(mapped, 79)).toBe(0)
    expect(findActiveWord(mapped, 80)).toBe(1)
    expect(findActiveWord(mapped, 399)).toBe(4)
  })

  it('no mapped timestamps is null', () => {
    expect(findActiveWord([], 500)).toBeNull()
  })
})

describe('PLAY-5: empty clips and skipped segments', () => {
  it('chains after a zero-length tail at the same startAt (gapless)', () => {
    const audio: ScheduleEntryView = { segmentId: 221, startAt: 10, durationSec: 2 }
    const empty: ScheduleEntryView = { segmentId: 222, startAt: 12, durationSec: 0 }
    expect(chainStart(audio, 11, false, 0.05)).toEqual({ when: 12, gap: false })
    expect(chainStart(empty, 11.5, false, 0.05)).toEqual({ when: 12, gap: false })
  })

  it('starts fresh (a gap) once the tail end has passed or while buffering', () => {
    const empty: ScheduleEntryView = { segmentId: 222, startAt: 12, durationSec: 0 }
    expect(chainStart(empty, 12.5, false, 0.05)).toEqual({ when: 12.55, gap: true })
    expect(chainStart(empty, 11, true, 0.05)).toEqual({ when: 11.05, gap: true })
  })

  it('locate passes over a zero-length entry to the clip chained at the same startAt', () => {
    const entries: ScheduleEntryView[] = [
      { segmentId: 221, startAt: 10, durationSec: 2 },
      { segmentId: 222, startAt: 12, durationSec: 0 },
      { segmentId: 223, startAt: 12, durationSec: 3 },
    ]
    expect(locate(entries, 11.9)?.segmentId).toBe(221)
    expect(locate(entries, 12)?.segmentId).toBe(223)
  })

  it('nextPlayable steps over skipped ids and is null past the end', () => {
    const ids = [220, 221, 222, 223]
    expect(nextPlayable(ids, 220, new Set())).toBe(221)
    expect(nextPlayable(ids, 221, new Set([222]))).toBe(223)
    expect(nextPlayable(ids, 221, new Set([222, 223]))).toBeNull()
    expect(nextPlayable(ids, 223, new Set())).toBeNull()
    expect(nextPlayable(ids, 999, new Set())).toBeNull()
  })

  it('a failed prefetch is skipped; only a failure on the target is an error', () => {
    expect(onFetchFailure(222, 220)).toBe('skip')
    expect(onFetchFailure(222, null)).toBe('skip')
    expect(onFetchFailure(220, 220)).toBe('error')
  })
})
