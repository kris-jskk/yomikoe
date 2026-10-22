// Reader (spec §7, PLAY-2, PLAY-3): segments rendered once as `.seg` elements with one `.w` span per
// whitespace token of `text` (offsets from `tokenize`, so X-Timestamps char offsets map onto them).
// The highlight is applied by usePlayer's rAF loop through the refs registered here, never by React.
// M4: a segment skipped by a PLAY-8 toggle gets the `skipped` class (rendered dimmed).
// M5 TERM-2: a word selected inside one segment shows a "Pronounce as" button that opens PronounceDialog;
// a save drops the clips of the segments holding the word, Listen plays the selected sentence.
// M5 MATH-5: tokens inside a maths range are not split: each range is one `.math` element (boxed when
// displayed, or inside an equation segment) that the highlight treats as one unit; an equation segment
// is highlighted whole while it plays (usePlayer `unitEl`).

import { memo, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import type { MathRange, PronunciationSaved, Section, Segment } from '../api/types'
import { tokenize, type Token } from '../player/schedule'
import { PronounceDialog, pickWord, segmentsWithWord } from './PronounceDialog'

export interface ReaderProps {
  segments: Segment[]
  sections: Section[]
  registerSegmentEl: (id: number, el: HTMLElement | null, tokens?: Token[]) => void
  /** The reading column element; the player listens for wheel/touchmove on it (stops follow mode). */
  registerReaderEl?: (el: HTMLElement | null) => void
  onSeek: (segmentId: number, tokenIndex?: number) => void
  /** PLAY-8: ids skipped by the toggles. */
  skipped?: ReadonlySet<number>
  /** TERM-2: the document a "this document" respelling is saved for; without it no button is shown. */
  documentId?: number
  /** TERM-2: after a save, the ids of the segments whose normalized_text holds the word. */
  onPronounceSaved?: (segmentIds: number[], saved: PronunciationSaved) => void
  /** TERM-2 Listen: play this segment through the player. */
  onListen?: (segmentId: number) => void
}

type WordPick = { segmentId: number; word: string; top: number; left: number }

/** The word selected inside a single `.seg` of `root`, with where to put the button; else null. */
function readSelection(root: HTMLElement | null): WordPick | null {
  const sel = typeof window === 'undefined' ? null : window.getSelection()
  if (!root || !sel || sel.rangeCount === 0 || sel.isCollapsed) return null
  const range = sel.getRangeAt(0)
  const node = range.commonAncestorContainer
  const el = node instanceof Element ? node : node.parentElement
  const segEl = el?.closest<HTMLElement>('.seg')
  if (!segEl || !root.contains(segEl)) return null
  const word = pickWord(sel.toString())
  if (word === null) return null
  const r = range.getBoundingClientRect()
  return { segmentId: Number(segEl.dataset.id), word, top: r.bottom + 4, left: r.left }
}

/** One rendered piece of a segment: a word span, or a maths range covering tokens from..to. */
export type Piece =
  | { kind: 'w'; i: number }
  | { kind: 'math'; from: number; to: number; display: boolean; text: string }

/**
 * MATH-5: split a segment's tokens into word pieces and maths pieces. A token overlapping a range joins
 * that range's piece (consecutive tokens of one range form one piece, its text the raw slice of `text`);
 * every other token is its own word piece, so token indices stay aligned with `tokenize`.
 */
export function segmentPieces(
  text: string,
  tokens: readonly Token[],
  math: readonly MathRange[] | undefined,
): Piece[] {
  const ranges = math ?? []
  const pieces: Piece[] = []
  let open: { r: number; from: number } | null = null
  const close = (to: number) => {
    if (open === null) return
    const r = ranges[open.r]
    pieces.push({
      kind: 'math',
      from: open.from,
      to,
      display: r.display,
      text: text.slice(tokens[open.from].charStart, tokens[to].charEnd),
    })
    open = null
  }
  tokens.forEach((t, i) => {
    const r = ranges.findIndex((m) => t.charStart < m.end && t.charEnd > m.start)
    if (open !== null && open.r !== r) close(i - 1)
    if (r < 0) pieces.push({ kind: 'w', i })
    else if (open === null) open = { r, from: i }
  })
  close(tokens.length - 1)
  return pieces
}

function SegmentView({
  seg,
  section,
  register,
  skipped,
}: {
  seg: Segment
  section: Section | undefined
  register: ReaderProps['registerSegmentEl']
  skipped: boolean
}) {
  const tokens = useMemo(() => tokenize(seg.text), [seg.text])
  const pieces = useMemo(
    () => segmentPieces(seg.text, tokens, seg.math),
    [seg.text, tokens, seg.math],
  )
  const children: (string | React.JSX.Element)[] = []
  pieces.forEach((p, k) => {
    if (k > 0) children.push(' ')
    children.push(
      p.kind === 'w' ? (
        <span key={k} className="w" data-i={p.i}>
          {tokens[p.i].token}
        </span>
      ) : (
        <span
          key={k}
          className={`math ${p.display ? 'math-display' : 'math-inline'}`}
          data-from={p.from}
          data-to={p.to}
        >
          {p.text}
        </span>
      ),
    )
  })
  const props = {
    className: `seg seg-${seg.type}${skipped ? ' skipped' : ''}`,
    'data-id': seg.id,
    'data-order': seg.order,
    ref: (el: HTMLElement | null) => register(seg.id, el, tokens),
  }
  // A derived section (spec §7 amendment) is its own heading segment: render that segment as the heading.
  if (section && seg.type === 'heading' && section.title === seg.text) {
    const H = section.level > 1 ? 'h3' : 'h2'
    return (
      <H id={`section-${section.id}`} {...props}>
        {children}
      </H>
    )
  }
  return (
    <>
      {section && (
        <h2 className="section-title" id={`section-${section.id}`}>
          {section.title}
        </h2>
      )}
      <p {...props}>{children}</p>
    </>
  )
}

function ReaderImpl({
  segments,
  sections,
  registerSegmentEl,
  registerReaderEl,
  onSeek,
  skipped,
  documentId,
  onPronounceSaved,
  onListen,
}: ReaderProps) {
  const byFirst = useMemo(() => new Map(sections.map((s) => [s.first_segment_id, s])), [sections])
  const articleEl = useRef<HTMLElement | null>(null)
  const setArticle = useCallback(
    (el: HTMLElement | null) => {
      articleEl.current = el
      registerReaderEl?.(el)
    },
    [registerReaderEl],
  )
  const [pick, setPick] = useState<WordPick | null>(null)
  const [dialog, setDialog] = useState<{ segmentId: number; word: string } | null>(null)
  const pronounce = documentId !== undefined
  useEffect(() => {
    if (!pronounce) return
    const onSel = () => setPick(readSelection(articleEl.current))
    document.addEventListener('selectionchange', onSel)
    return () => document.removeEventListener('selectionchange', onSel)
  }, [pronounce])
  const closeDialog = useCallback(() => setDialog(null), [])
  const onSaved = useCallback(
    (saved: PronunciationSaved) =>
      onPronounceSaved?.(segmentsWithWord(segments, saved.word), saved),
    [segments, onPronounceSaved],
  )
  const onClick = (e: MouseEvent<HTMLElement>) => {
    // a drag that selects text (to pick a word) is not a click to seek
    const sel = window.getSelection()
    if (pronounce && sel && !sel.isCollapsed) return
    const target = e.target as HTMLElement
    const segEl = target.closest<HTMLElement>('.seg')
    if (!segEl) return
    const id = Number(segEl.dataset.id)
    // MATH-5: an equation segment is one unit (seek to its start); a maths range seeks to its first token
    if (segEl.classList.contains('seg-equation')) return onSeek(id)
    const w = target.closest<HTMLElement>('.w')
    const m = target.closest<HTMLElement>('.math')
    if (w && segEl.contains(w)) onSeek(id, Number(w.dataset.i))
    else if (m && segEl.contains(m)) onSeek(id, Number(m.dataset.from))
    else onSeek(id)
  }
  return (
    <>
      <article className="reader" ref={setArticle} onClick={onClick}>
        {segments.map((seg) => (
          <SegmentView
            key={seg.id}
            seg={seg}
            section={byFirst.get(seg.id)}
            register={registerSegmentEl}
            skipped={skipped?.has(seg.id) ?? false}
          />
        ))}
      </article>
      {pronounce && pick !== null && dialog === null && (
        <button
          type="button"
          className="pronounce-btn"
          style={{ position: 'fixed', top: pick.top, left: pick.left }}
          // keep the selection while the button takes the click
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setDialog({ segmentId: pick.segmentId, word: pick.word })}
        >
          Pronounce as
        </button>
      )}
      {pronounce && dialog !== null && (
        <PronounceDialog
          key={`${dialog.segmentId}:${dialog.word}`}
          word={dialog.word}
          documentId={documentId}
          onSaved={onSaved}
          onListen={() => onListen?.(dialog.segmentId)}
          onClose={closeDialog}
        />
      )}
    </>
  )
}

export const Reader = memo(ReaderImpl)

/**
 * Sections for the Toc and SKIP_SECTION (spec §7 amendment): the API's when non-empty, else one per
 * segment of type `heading`, titled by its text, first_segment_id = its id.
 */
export function deriveSections(apiSections: Section[], segments: Segment[]): Section[] {
  if (apiSections.length > 0) return apiSections
  return segments
    .filter((s) => s.type === 'heading')
    .map((s) => ({ id: s.id, title: s.text, level: 1, first_segment_id: s.id }))
}
