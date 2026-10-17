// Reader (spec §7, PLAY-2, PLAY-3): segments rendered once as `.seg` elements with one `.w` span per
// whitespace token of `text` (offsets from `tokenize`, so X-Timestamps char offsets map onto them).
// The highlight is applied by usePlayer's rAF loop through the refs registered here, never by React.

import { memo, useMemo, type MouseEvent } from 'react'
import type { Section, Segment } from '../api/types'
import { tokenize, type Token } from '../player/schedule'

export interface ReaderProps {
  segments: Segment[]
  sections: Section[]
  registerSegmentEl: (id: number, el: HTMLElement | null, tokens?: Token[]) => void
  /** The reading column element; the player listens for wheel/touchmove on it (stops follow mode). */
  registerReaderEl?: (el: HTMLElement | null) => void
  onSeek: (segmentId: number, tokenIndex?: number) => void
}

function SegmentView({
  seg,
  section,
  register,
}: {
  seg: Segment
  section: Section | undefined
  register: ReaderProps['registerSegmentEl']
}) {
  const tokens = useMemo(() => tokenize(seg.text), [seg.text])
  const children: (string | React.JSX.Element)[] = []
  tokens.forEach((t, i) => {
    if (i > 0) children.push(' ')
    children.push(
      <span key={i} className="w" data-i={i}>
        {t.token}
      </span>,
    )
  })
  const props = {
    className: `seg seg-${seg.type}`,
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
}: ReaderProps) {
  const byFirst = useMemo(() => new Map(sections.map((s) => [s.first_segment_id, s])), [sections])
  const onClick = (e: MouseEvent<HTMLElement>) => {
    const target = e.target as HTMLElement
    const segEl = target.closest<HTMLElement>('.seg')
    if (!segEl) return
    const id = Number(segEl.dataset.id)
    const w = target.closest<HTMLElement>('.w')
    if (w && segEl.contains(w)) onSeek(id, Number(w.dataset.i))
    else onSeek(id)
  }
  return (
    <article className="reader" ref={registerReaderEl} onClick={onClick}>
      {segments.map((seg) => (
        <SegmentView
          key={seg.id}
          seg={seg}
          section={byFirst.get(seg.id)}
          register={registerSegmentEl}
        />
      ))}
    </article>
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
