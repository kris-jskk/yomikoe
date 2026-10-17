// Pure timing helpers for scheduling and highlight (D5, D8; spec _agent/specs/m3-reader-interfaces.md §6).
// Phase 1 stub: the types and signatures are fixed here; the bodies are implemented in phase 2.

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
  void text
  throw new Error('NotImplemented: tokenize')
}

export function mapTimestampsToTokens(tokens: Token[], ts: WordTimestamp[]): MappedTimestamp[] {
  void tokens
  void ts
  throw new Error('NotImplemented: mapTimestampsToTokens')
}

export function locate(
  entries: ScheduleEntryView[],
  currentTime: number,
): { segmentId: number; elapsedMs: number } | null {
  void entries
  void currentTime
  throw new Error('NotImplemented: locate')
}

/** Token index of the last mapped timestamp with `start_ms <= elapsedMs`, or null before the first. */
export function findActiveWord(mapped: MappedTimestamp[], elapsedMs: number): number | null {
  void mapped
  void elapsedMs
  throw new Error('NotImplemented: findActiveWord')
}
