// Hash router (spec §3): "#/" -> Picker, "#/doc/{id}" -> Reader + Toc + PlayerBar.

import { DEFAULT_SPEED } from './player/machine'
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { getAllSegments, getDocument, getVoices } from './api/client'
import type { DocumentDetail, Segment, Voice } from './api/types'
import { Picker } from './components/Picker'
import { PlayerBar } from './components/PlayerBar'
import { Reader, deriveSections } from './components/Reader'
import { Toc } from './components/Toc'
import { usePlayer } from './player/usePlayer'

function subscribeHash(cb: () => void) {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

function useHash(): string {
  return useSyncExternalStore(subscribeHash, () => window.location.hash)
}

interface Loaded {
  doc: DocumentDetail
  segments: Segment[]
  voices: Voice[]
}

function orderedHas(segments: Segment[], pos: { segment_id: number }): boolean {
  return segments.some((s) => s.id === pos.segment_id)
}

function DocView({ documentId }: { documentId: number }) {
  const player = usePlayer()
  const { dispatch, registerSegmentEl, registerReaderEl, seekTo } = player
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    Promise.all([
      getDocument(documentId, ctrl.signal),
      getAllSegments(documentId, undefined, ctrl.signal),
      getVoices(ctrl.signal),
    ]).then(
      ([doc, segments, voices]) => {
        if (ctrl.signal.aborted) return
        const sections = deriveSections(doc.sections, segments)
        dispatch({
          type: 'LOAD',
          documentId,
          orderedIds: segments.map((s) => s.id),
          sectionStarts: sections.map((s) => s.first_segment_id),
          voice: doc.settings?.voice_id ?? voices[0]?.id ?? '',
          speed: doc.settings?.speed ?? DEFAULT_SPEED,
          // the API may return a position object with null fields for a never-played document
          position:
            doc.position && doc.position.segment_id != null && orderedHas(segments, doc.position)
              ? { segmentId: doc.position.segment_id, offsetMs: doc.position.offset_ms ?? 0 }
              : undefined,
        })
        setLoaded({ doc, segments, voices })
      },
      (e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      },
    )
    return () => ctrl.abort()
  }, [documentId, dispatch])

  const sections = useMemo(
    () => (loaded ? deriveSections(loaded.doc.sections, loaded.segments) : []),
    [loaded],
  )
  const onSeek = useCallback((id: number, i?: number) => seekTo(id, i), [seekTo])

  if (error)
    return (
      <p className="error-box">
        Could not load document {documentId}: {error}
      </p>
    )
  if (!loaded) return <p className="picker">Loading document…</p>
  return (
    <>
      <div className="doc">
        <Toc sections={sections} onSeek={onSeek} />
        <Reader
          segments={loaded.segments}
          sections={sections}
          registerSegmentEl={registerSegmentEl}
          registerReaderEl={registerReaderEl}
          onSeek={onSeek}
        />
      </div>
      <PlayerBar player={player} voices={loaded.voices} />
    </>
  )
}

export default function App() {
  const hash = useHash()
  const m = /^#\/doc\/(\d+)$/.exec(hash)
  return (
    <>
      <header className="app-header">
        <h1>
          <a href="#/">HearNarro</a>
        </h1>
      </header>
      <main>{m ? <DocView key={m[1]} documentId={Number(m[1])} /> : <Picker />}</main>
    </>
  )
}
