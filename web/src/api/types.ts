// Wire and client types for the reader (spec _agent/specs/m3-reader-interfaces.md §1, §4).

export interface WordTimestamp {
  word: string
  start_ms: number
  end_ms: number
  char_start: number
  char_end: number
}

export interface Segment {
  id: number
  order: number
  block_id: number
  type: string
  section_id: number | null
  text: string
  normalized_text: string
  char_start: number
  char_end: number
}

export interface Section {
  id: number
  title: string
  level: number
  first_segment_id: number
}

export interface Voice {
  id: string
  name: string
  gender: string
  language: string
  /** Present on the wire (`routes/voices.py`); not used by the reader. */
  backend?: string
}

export interface AudioClip {
  segmentId: number
  voice: string
  speed: number
  buffer: AudioBuffer
  timestamps: WordTimestamp[]
  durationMs: number
  mediaType: string
  fetchMs: number
  decodeMs: number
}

/** One row of `GET /documents`. */
export interface DocumentSummary {
  id: number
  title: string
  filename: string
  page_count: number
  pages_done: number
  status: string
}

export interface DocumentSettings {
  voice_id: string | null
  speed: number | null
}

export interface DocumentPosition {
  segment_id: number
  offset_ms: number
}

/** `GET /documents/{id}`: the summary plus sections, settings and position (the last two may be null). */
export interface DocumentDetail extends DocumentSummary {
  sections: Section[]
  settings: DocumentSettings | null
  position: DocumentPosition | null
}

/** `GET /documents/{id}/segments?from=&limit=`. */
export interface SegmentsPage {
  document_id: number
  total: number
  from: number
  limit: number
  next_from: number | null
  segments: Segment[]
}
