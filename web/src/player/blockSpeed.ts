// PLAY-11 block speed (red stub; implemented in the next commit).
export const BLOCK_FACTOR_MIN = 0
export const BLOCK_FACTOR_MAX = 0
export const DEFAULT_BLOCK_SPEED = { equation: 0 }
export function clampBlockFactor(_f: number): number {
  throw new Error('not implemented')
}
export function segmentSpeed(_type: string, _speed: number, _factors: { equation: number }): number {
  throw new Error('not implemented')
}
