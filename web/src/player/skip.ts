// PLAY-8 skip rules (spec _agent/specs/m4-library-interfaces.md §2, "Skip toggles"). Pure.

import type { Segment } from '../api/types'

export interface SkipState {
  footnotes: boolean
  captions: boolean
  references: boolean
}

export const NO_SKIP: SkipState = { footnotes: false, captions: false, references: false }

/** A heading that opens the references span. */
export const REFERENCES_HEADING = /^(references|bibliography|works cited)\b/i

/** Ids from each references heading up to (not including) the next heading; segments in reading order. */
export function referenceIds(segments: Segment[]): Set<number> {
  const out = new Set<number>()
  let inRefs = false
  for (const s of segments) {
    if (s.type === 'heading') inRefs = REFERENCES_HEADING.test(s.text.trim())
    if (inRefs) out.add(s.id)
  }
  return out
}

export function isSkipped(segment: Segment, skip: SkipState, refs: Set<number>): boolean {
  if (skip.footnotes && segment.type === 'footnote') return true
  if (skip.captions && segment.type === 'caption') return true
  return skip.references && refs.has(segment.id)
}

/** Every skipped id, in the order of `segments`. */
export function skippedIds(segments: Segment[], skip: SkipState): number[] {
  if (!skip.footnotes && !skip.captions && !skip.references) return []
  const refs = skip.references ? referenceIds(segments) : new Set<number>()
  return segments.filter((s) => isSkipped(s, skip, refs)).map((s) => s.id)
}

/** `id` if not skipped, else the first unskipped id from it in direction `dir`; null if none or unknown. */
export function nextUnskipped(
  orderedIds: number[],
  id: number,
  skipped: Set<number>,
  dir: 1 | -1 = 1,
): number | null {
  let i = orderedIds.indexOf(id)
  if (i < 0) return null
  for (; i >= 0 && i < orderedIds.length; i += dir) {
    if (!skipped.has(orderedIds[i])) return orderedIds[i]
  }
  return null
}
