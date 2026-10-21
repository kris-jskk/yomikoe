// PLAY-11: per-block playback speed (spec _agent/specs/m5-academic-reading.md §4d). Pure.
import { describe, expect, it } from 'vitest'

import {
  BLOCK_FACTOR_MAX,
  BLOCK_FACTOR_MIN,
  DEFAULT_BLOCK_SPEED,
  clampBlockFactor,
  segmentSpeed,
} from '../../src/player/blockSpeed'

const F = { equation: 0.8 }

describe('PLAY-11 segmentSpeed', () => {
  it('PLAY-11 equation plays at speed x factor: 1.25 x 0.8 = 1.0', () => {
    expect(segmentSpeed('equation', 1.25, F)).toBe(1.0)
  })

  it('PLAY-11 clamps to the speed floor: 0.5 x 0.5 = 0.5', () => {
    expect(segmentSpeed('equation', 0.5, { equation: 0.5 })).toBe(0.5)
  })

  it('PLAY-11 prose, captions and footnotes play at the document speed', () => {
    expect(segmentSpeed('paragraph', 3.0, F)).toBe(3.0)
    expect(segmentSpeed('caption', 1.35, F)).toBe(1.35)
    expect(segmentSpeed('footnote', 0.75, F)).toBe(0.75)
    expect(segmentSpeed('heading', 1.25, F)).toBe(1.25)
  })

  it('PLAY-11 rounds to the 0.05 grid: 1.75 x 0.8 = 1.4, 1.1 x 0.85 = 0.95', () => {
    expect(segmentSpeed('equation', 1.75, F)).toBe(1.4)
    expect(segmentSpeed('equation', 1.1, { equation: 0.85 })).toBe(0.95)
    expect(segmentSpeed('equation', 3.0, { equation: 1.0 })).toBe(3.0)
  })

  it('PLAY-11 the settings-key form is stable (toFixed(2))', () => {
    expect(segmentSpeed('equation', 1.75, F).toFixed(2)).toBe('1.40')
    expect(segmentSpeed('equation', 1.25, F).toFixed(2)).toBe('1.00')
    expect(segmentSpeed('equation', 2.95, F).toFixed(2)).toBe('2.35')
    for (let i = 10; i <= 60; i++) {
      const v = segmentSpeed('equation', i / 20, F)
      expect(Math.round(v * 20) / 20).toBe(v)
    }
  })

  it('PLAY-11 clampBlockFactor keeps the factor in [0.5, 1.0] on the 0.05 grid', () => {
    expect(DEFAULT_BLOCK_SPEED).toEqual({ equation: 0.8 })
    expect(BLOCK_FACTOR_MIN).toBe(0.5)
    expect(BLOCK_FACTOR_MAX).toBe(1.0)
    expect(clampBlockFactor(0.2)).toBe(0.5)
    expect(clampBlockFactor(1.5)).toBe(1.0)
    expect(clampBlockFactor(0.77)).toBe(0.75)
  })
})
