// LIB-1: library table formatting helpers (spec _agent/specs/m4-library-interfaces.md §2, "Library").
import { describe, expect, it } from 'vitest'

import { formatLastOpened, formatProgress } from '../../src/components/libraryFormat'

describe('LIB-1 formatProgress', () => {
  it('LIB-1 whole percent, rounded down so 100% means finished', () => {
    expect(formatProgress(0)).toBe('0%')
    expect(formatProgress(0.42)).toBe('42%')
    expect(formatProgress(0.426)).toBe('42%')
    expect(formatProgress(0.999)).toBe('99%')
    expect(formatProgress(1)).toBe('100%')
  })

  it('LIB-1 out-of-range and non-finite values clamp to [0%, 100%]', () => {
    expect(formatProgress(-0.1)).toBe('0%')
    expect(formatProgress(1.5)).toBe('100%')
    expect(formatProgress(Number.NaN)).toBe('0%')
  })
})

describe('LIB-1 formatLastOpened', () => {
  const now = new Date('2026-10-17T12:00:00Z')
  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString()
  const MIN = 60_000
  const HOUR = 60 * MIN
  const DAY = 24 * HOUR

  it('LIB-1 null means never opened', () => {
    expect(formatLastOpened(null, now)).toBe('never')
  })

  it('LIB-1 under a minute is "just now" (also for a slightly future clock)', () => {
    expect(formatLastOpened(ago(30_000), now)).toBe('just now')
    expect(formatLastOpened(ago(-5_000), now)).toBe('just now')
  })

  it('LIB-1 minutes, hours, days', () => {
    expect(formatLastOpened(ago(MIN), now)).toBe('1 min ago')
    expect(formatLastOpened(ago(5 * MIN), now)).toBe('5 min ago')
    expect(formatLastOpened(ago(HOUR), now)).toBe('1 hour ago')
    expect(formatLastOpened(ago(3 * HOUR), now)).toBe('3 hours ago')
    expect(formatLastOpened(ago(DAY), now)).toBe('yesterday')
    expect(formatLastOpened(ago(4 * DAY), now)).toBe('4 days ago')
  })

  it('LIB-1 a week or older shows the date (YYYY-MM-DD)', () => {
    expect(formatLastOpened(ago(7 * DAY), now)).toBe('2026-10-10')
    expect(formatLastOpened('2025-01-02T12:00:00Z', now)).toBe('2025-01-02')
  })

  it('LIB-1 an unparseable timestamp is "never", not "NaN"', () => {
    expect(formatLastOpened('not a date', now)).toBe('never')
  })
})
