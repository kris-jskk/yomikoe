// SYN-8 pauses (spec _agent/specs/m5-academic-reading.md §4e, §8 Q7). Pure.
// A pause is a client-side start-time gap after a segment, keyed by its block type; the audio cache is
// untouched (still keyed by segment, voice, speed), so lengths can change without re-synthesis.

/** Pause after a segment of each block type, ms; any other type has no pause. */
export const PAUSE_MS: Readonly<Record<string, number>> = Object.freeze({
  heading: 600,
  list: 250,
  equation: 400,
})

/** The pause after a segment of block type `type`, ms (0 for types not in PAUSE_MS). */
export function pauseAfterMs(type: string): number {
  return Object.prototype.hasOwnProperty.call(PAUSE_MS, type) ? PAUSE_MS[type] : 0
}
