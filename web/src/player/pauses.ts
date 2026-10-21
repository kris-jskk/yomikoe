// SYN-8 pauses (red stub; implemented in the next commit).
export const PAUSE_MS: Readonly<Record<string, number>> = {}
export function pauseAfterMs(_type: string): number {
  throw new Error('not implemented')
}
