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
  /** Null for an empty clip (no samples: header-only WAV or X-Duration-Ms 0); it is never decoded. */
  buffer: AudioBuffer | null
  /** Playable length in seconds: the decoded buffer's duration, or 0 for an empty clip (PLAY-5). */
  durationSec: number
  timestamps: WordTimestamp[]
  durationMs: number
  mediaType: string
  fetchMs: number
  decodeMs: number
}

export interface DocumentSettings {
  voice_id: string | null
  speed: number | null
}

/**
 * Stored position on the wire. NOTE: an unset position arrives as `{segment_id: null, offset_ms: 0}`
 * (M4 deviation 3); `segment_id` stays typed `number` until App.tsx (UI worker) narrows it, so every
 * reader must still check `segment_id != null`.
 */
export interface DocumentPosition {
  segment_id: number
  offset_ms: number
}

/** One row of `GET /documents` (LIB-1); also the body `PATCH /documents/{id}` returns. */
export interface DocumentSummary {
  id: number
  title: string
  filename: string
  page_count: number
  pages_done: number
  status: string
  segment_count: number
  /** Null tolerated for older servers; the M4 API sends the null-fields object instead. */
  position: DocumentPosition | null
  /** Fraction of segments before the saved position, in [0, 1]. */
  progress: number
  settings: DocumentSettings | null
  last_opened_at: string | null
  /** ING-11 (D40): absent from servers before M5. */
  profile?: DocumentProfile
  /** Only on a PATCH that changed the profile: segments re-normalized, cache rows removed. */
  renormalized?: { changed: number; removed: number }
}

export type ProfileClass = 'prose' | 'mixed' | 'math'

/** ING-11 document profile: effective class (override wins), computed class and raw shares. */
export interface DocumentProfile {
  class: ProfileClass
  computed_class: ProfileClass
  override: ProfileClass | null
  math_share: number
  display_per_page: number
  inline_token_share: number
  code_share: number
  citation_style: 'numeric' | 'author_year' | 'none'
  scanned_share: number
  author_year_citations: 'read' | 'skip'
}

/** `GET /documents/{id}`: the summary plus sections. */
export interface DocumentDetail extends DocumentSummary {
  sections: Section[]
}

/** `PATCH /documents/{id}` body (LIB-2, LIB-3); every field optional. */
export interface DocumentPatch {
  position?: { segment_id: number; offset_ms: number }
  settings?: DocumentSettings
  opened?: boolean
  /** ING-11: `class: null` clears the override; a change re-normalizes on the server. */
  profile?: { class?: ProfileClass | null; author_year_citations?: 'read' | 'skip' }
}

/** `GET` / `PUT /settings`: global defaults (LIB-3). */
export interface GlobalSettings {
  default_voice_id: string | null
  default_speed: number
}

/** `POST /documents` response: 202 for a new upload, 200 for an already-known file. */
export interface UploadResult {
  id: number
  status: string
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

/** TERM-2: one row of `GET /pronunciations`; `document_id` null is a global override. */
export interface Pronunciation {
  id: number
  document_id: number | null
  /** Stored lower-cased by the server. */
  word: string
  respelling: string
  created_at: string
}

/** `PUT /pronunciations` body: `document_id` null saves for all documents. */
export interface PronunciationPut {
  document_id: number | null
  word: string
  respelling: string
}

/** `PUT /pronunciations` response: the row plus how many segments' cached audio was purged. */
export interface PronunciationSaved extends Pronunciation {
  invalidated: number
}

/** `DELETE /pronunciations/{id}` response. */
export interface PronunciationDeleted {
  invalidated: number
}
