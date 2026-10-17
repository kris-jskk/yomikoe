// Pure timing helpers for scheduling and highlight (D5, D8; spec _agent/specs/m3-reader-interfaces.md §6).

import type { WordTimestamp } from '../api/types'

/** A whitespace-delimited token of a segment's `text`, with offsets into `text` (`[charStart, charEnd)`). */
export interface Token {
  token: string
  charStart: number
  charEnd: number
}

/** A word timestamp assigned to the token it overlaps. */
export interface MappedTimestamp {
  start_ms: number
  end_ms: number
  tokenIndex: number
}

/** The part of a schedule entry the pure helpers need (the hook's entry also holds the source node). */
export interface ScheduleEntryView {
  segmentId: number
  /** AudioContext time at which offset 0 of the clip plays. */
  startAt: number
  durationSec: number
}

export function tokenize(text: string): Token[] {
  const tokens: Token[] = []
  const re = /\S+/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    tokens.push({ token: m[0], charStart: m.index, charEnd: m.index + m[0].length })
  }
  return tokens
}

/**
 * Assign every timestamp to the first token whose `[charStart, charEnd)` overlaps the timestamp's
 * `[char_start, char_end)`; a timestamp overlapping no token is dropped.
 */
export function mapTimestampsToTokens(tokens: Token[], ts: WordTimestamp[]): MappedTimestamp[] {
  const out: MappedTimestamp[] = []
  for (const t of ts) {
    // first token whose end is past the timestamp's start (tokens are sorted and disjoint)
    let lo = 0
    let hi = tokens.length
    while (lo < hi) {
      const mid = (lo + hi) >>> 1
      if (tokens[mid].charEnd <= t.char_start) lo = mid + 1
      else hi = mid
    }
    if (lo < tokens.length && tokens[lo].charStart < t.char_end && t.char_start < t.char_end) {
      out.push({ start_ms: t.start_ms, end_ms: t.end_ms, tokenIndex: lo })
    }
  }
  return out
}

/**
 * The entry with the largest `startAt <= currentTime` whose window `[startAt, startAt + durationSec)`
 * contains `currentTime`, and the elapsed time into it; null in a gap, before the first or after the last.
 * `entries` must be sorted by `startAt`.
 */
export function locate(
  entries: ScheduleEntryView[],
  currentTime: number,
): { segmentId: number; elapsedMs: number } | null {
  let lo = 0
  let hi = entries.length
  while (lo < hi) {
    const mid = (lo + hi) >>> 1
    if (entries[mid].startAt <= currentTime) lo = mid + 1
    else hi = mid
  }
  const i = lo - 1
  if (i < 0) return null
  const e = entries[i]
  const elapsed = currentTime - e.startAt
  if (elapsed >= e.durationSec) return null
  return { segmentId: e.segmentId, elapsedMs: elapsed * 1000 }
}

/** Token index of the last mapped timestamp with `start_ms <= elapsedMs`, or null before the first. */
export function findActiveWord(mapped: MappedTimestamp[], elapsedMs: number): number | null {
  let lo = 0
  let hi = mapped.length
  while (lo < hi) {
    const mid = (lo + hi) >>> 1
    if (mapped[mid].start_ms <= elapsedMs) lo = mid + 1
    else hi = mid
  }
  return lo === 0 ? null : mapped[lo - 1].tokenIndex
}

/**
 * Where the clip after `tail` starts (PLAY-5). Chained at `tail.startAt + tail.durationSec` while that
 * is still ahead of `now` and the schedule is not buffering (a zero-length tail chains at its own
 * startAt: gapless); otherwise freshly at `now + leadSec`, which is a gap.
 */
export function chainStart(
  tail: ScheduleEntryView,
  now: number,
  buffering: boolean,
  leadSec: number,
): { when: number; gap: boolean } {
  const end = tail.startAt + tail.durationSec
  if (!buffering && end > now) return { when: end, gap: false }
  return { when: now + leadSec, gap: true }
}

/** The first id after `afterId` in reading order that is not in `skipped`, or null past the end. */
export function nextPlayable(
  orderedIds: number[],
  afterId: number,
  skipped: ReadonlySet<number>,
): number | null {
  const i = orderedIds.indexOf(afterId)
  if (i < 0) return null
  for (let j = i + 1; j < orderedIds.length; j++) {
    if (!skipped.has(orderedIds[j])) return orderedIds[j]
  }
  return null
}

/**
 * What a failed fetch does (PLAY-5): a failure on the segment the schedule is blocked on (`targetId`:
 * the play/seek target, or the next clip while buffering) is an error; any other failure is a
 * prefetch, which is skipped so playback continues past it.
 */
export function onFetchFailure(failedId: number, targetId: number | null): 'error' | 'skip' {
  return failedId === targetId ? 'error' : 'skip'
}
