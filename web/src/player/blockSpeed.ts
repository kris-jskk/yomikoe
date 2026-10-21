// PLAY-11 per-block speed (spec _agent/specs/m5-academic-reading.md §4d). Pure.
// Equations play at the document speed times a factor; every other block type (captions and footnotes
// included) plays at the document speed.

import { SPEED_MAX, SPEED_MIN } from './keys'

/** Per-block-type speed factors. */
export interface BlockSpeed {
  equation: number
}

export const BLOCK_FACTOR_MIN = 0.5
export const BLOCK_FACTOR_MAX = 1.0
export const DEFAULT_BLOCK_SPEED: BlockSpeed = Object.freeze({ equation: 0.8 })

/** Round to the 0.05 grid. */
function grid(v: number): number {
  return Math.round(v * 20) / 20
}

/** A factor clamped to [BLOCK_FACTOR_MIN, BLOCK_FACTOR_MAX] on the 0.05 grid. */
export function clampBlockFactor(factor: number): number {
  return Math.min(BLOCK_FACTOR_MAX, Math.max(BLOCK_FACTOR_MIN, grid(factor)))
}

/**
 * The speed a segment of block type `type` is requested at: `speed × factors.equation` for an
 * equation, rounded to the 0.05 grid and clamped to [SPEED_MIN, SPEED_MAX]; `speed` for any other type.
 */
export function segmentSpeed(type: string, speed: number, factors: BlockSpeed): number {
  if (type !== 'equation') return speed
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, grid(speed * factors.equation)))
}
