// Toc (spec §7): the sections list; a click seeks to the section's first segment (PLAY if idle).

import { memo } from 'react'
import type { Section } from '../api/types'

export interface TocProps {
  sections: Section[]
  onSeek: (segmentId: number) => void
}

function TocImpl({ sections, onSeek }: TocProps) {
  if (sections.length === 0) return <nav className="toc" aria-label="Contents" />
  return (
    <nav className="toc" aria-label="Contents">
      <strong>Contents</strong>
      <ol>
        {sections.map((s) => (
          <li key={s.id} style={{ paddingLeft: `${(s.level - 1) * 0.75}rem` }}>
            <button type="button" onClick={() => onSeek(s.first_segment_id)}>
              {s.title}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}

export const Toc = memo(TocImpl)
