// PLAY-8: skip rules (spec _agent/specs/m4-library-interfaces.md §2, "Skip toggles"). Pure.
import { describe, expect, it } from 'vitest'

import type { Segment } from '../../src/api/types'
import {
  NO_SKIP,
  REFERENCES_HEADING,
  isSkipped,
  nextUnskipped,
  referenceIds,
  skippedIds,
  type SkipState,
} from '../../src/player/skip'

function seg(id: number, type: string, text = `s${id}`): Segment {
  return {
    id,
    order: id,
    block_id: id,
    type,
    section_id: null,
    text,
    normalized_text: text,
    char_start: 0,
    char_end: text.length,
  }
}

// 1 heading, 2 body, 3 footnote, 4 caption, 5 heading "References", 6-7 body (refs),
// 8 heading "Appendix", 9 body, 10 footnote
const SEGS: Segment[] = [
  seg(1, 'heading', 'Introduction'),
  seg(2, 'paragraph'),
  seg(3, 'footnote'),
  seg(4, 'caption'),
  seg(5, 'heading', 'References'),
  seg(6, 'paragraph', 'Smith, J. 2020.'),
  seg(7, 'list', 'Doe, A. 2021.'),
  seg(8, 'heading', 'Appendix'),
  seg(9, 'paragraph'),
  seg(10, 'footnote'),
]
const IDS = SEGS.map((s) => s.id)
const ALL: SkipState = { footnotes: true, captions: true, references: true }

describe('PLAY-8 references span', () => {
  it.each(['References', 'references', 'Bibliography', 'Works Cited', 'REFERENCES and notes'])(
    'PLAY-8 heading %j matches the references pattern',
    (t) => {
      expect(REFERENCES_HEADING.test(t)).toBe(true)
    },
  )

  it.each(['Referenced works', 'Further references', 'Introduction'])(
    'PLAY-8 heading %j does not match',
    (t) => {
      expect(REFERENCES_HEADING.test(t)).toBe(false)
    },
  )

  it('PLAY-8 span runs from the matching heading up to (not including) the next heading', () => {
    expect([...referenceIds(SEGS)].sort((a, b) => a - b)).toEqual([5, 6, 7])
  })

  it('PLAY-8 span with no following heading runs to the end', () => {
    const segs = [
      seg(1, 'heading', 'Body'),
      seg(2, 'paragraph'),
      seg(3, 'heading', 'Bibliography'),
      seg(4, 'paragraph'),
    ]
    expect([...referenceIds(segs)].sort((a, b) => a - b)).toEqual([3, 4])
  })

  it('PLAY-8 no references heading gives an empty span', () => {
    expect(referenceIds([seg(1, 'heading', 'Intro'), seg(2, 'paragraph')]).size).toBe(0)
  })
})

describe('PLAY-8 isSkipped', () => {
  const refs = referenceIds(SEGS)

  it('PLAY-8 nothing is skipped with every toggle off', () => {
    for (const s of SEGS) expect(isSkipped(s, NO_SKIP, refs)).toBe(false)
  })

  it('PLAY-8 footnotes toggle skips footnote segments only', () => {
    const skip = { ...NO_SKIP, footnotes: true }
    expect(SEGS.filter((s) => isSkipped(s, skip, refs)).map((s) => s.id)).toEqual([3, 10])
  })

  it('PLAY-8 captions toggle skips caption segments only', () => {
    const skip = { ...NO_SKIP, captions: true }
    expect(SEGS.filter((s) => isSkipped(s, skip, refs)).map((s) => s.id)).toEqual([4])
  })

  it('PLAY-8 references toggle skips the references span only', () => {
    const skip = { ...NO_SKIP, references: true }
    expect(SEGS.filter((s) => isSkipped(s, skip, refs)).map((s) => s.id)).toEqual([5, 6, 7])
  })

  it('PLAY-8 skippedIds combines the toggles in reading order', () => {
    expect(skippedIds(SEGS, ALL)).toEqual([3, 4, 5, 6, 7, 10])
    expect(skippedIds(SEGS, NO_SKIP)).toEqual([])
  })
})

describe('PLAY-8 nextUnskipped (used by skip and seek)', () => {
  const skipped = new Set(skippedIds(SEGS, ALL))

  it('PLAY-8 an unskipped id returns itself', () => {
    expect(nextUnskipped(IDS, 2, skipped)).toBe(2)
  })

  it('PLAY-8 forward jumps over a skipped run', () => {
    expect(nextUnskipped(IDS, 3, skipped)).toBe(8)
    expect(nextUnskipped(IDS, 3, skipped, 1)).toBe(8)
  })

  it('PLAY-8 backward jumps over a skipped run', () => {
    expect(nextUnskipped(IDS, 7, skipped, -1)).toBe(2)
  })

  it('PLAY-8 null when nothing unskipped remains in that direction', () => {
    expect(nextUnskipped(IDS, 10, skipped)).toBeNull()
    expect(nextUnskipped([3, 4], 3, skipped, -1)).toBeNull()
  })

  it('PLAY-8 null for an id not in the order', () => {
    expect(nextUnskipped(IDS, 999, skipped)).toBeNull()
  })
})
