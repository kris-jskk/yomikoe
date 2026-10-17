// Hash router (spec §3; M4 spec §2): "#/" -> Library, "#/doc/{id}" -> Reader + Toc + PlayerBar.
// DocView loads the document, its segments, the voices and the global settings, then LOAD, SET_SKIP (the
// per-document toggles from localStorage, PLAY-8) and RESTORE_POSITION (LIB-2), and sends `opened` once.

import { DEFAULT_SPEED } from './player/machine'
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { getAllSegments, getDocument, getSettings, getVoices, patchDocument } from './api/client'
import type { DocumentDetail, GlobalSettings, Segment, Voice } from './api/types'
import { Library } from './components/Library'
import { PlayerBar } from './components/PlayerBar'
import { Reader, deriveSections } from './components/Reader'
import { Toc } from './components/Toc'
import { NO_SKIP, skippedIds, type SkipState } from './player/skip'
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

/** PLAY-8 toggles persist per document in localStorage (a per-viewer convenience; may be unavailable). */
const skipKey = (documentId: number) => `hearnarro.skip.${documentId}`

function readSkip(documentId: number): SkipState {
  try {
    const raw = window.localStorage.getItem(skipKey(documentId))
    if (!raw) return NO_SKIP
    const v = JSON.parse(raw) as Partial<SkipState>
    return { footnotes: !!v.footnotes, captions: !!v.captions, references: !!v.references }
  } catch {
    return NO_SKIP
  }
}

function writeSkip(documentId: number, skip: SkipState) {
  try {
    window.localStorage.setItem(skipKey(documentId), JSON.stringify(skip))
  } catch {
    /* storage unavailable: the toggles last for this visit only */
  }
}

function DocView({ documentId }: { documentId: number }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const player = usePlayer({ title: loaded?.doc.title || loaded?.doc.filename })
  const { dispatch, registerSegmentEl, registerReaderEl, seekTo, revealSegment } = player
  const [restoreId, setRestoreId] = useState<number | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    Promise.all([
      getDocument(documentId, ctrl.signal),
      getAllSegments(documentId, undefined, ctrl.signal),
      getVoices(ctrl.signal),
      // LIB-3: global defaults apply only where the document has no setting of its own
      getSettings(ctrl.signal).catch((): GlobalSettings | null => null),
    ]).then(
      ([doc, segments, voices, globals]) => {
        if (ctrl.signal.aborted) return
        const sections = deriveSections(doc.sections, segments)
        const voiceIds = new Set(voices.map((v) => v.id))
        const globalVoice =
          globals?.default_voice_id && voiceIds.has(globals.default_voice_id)
            ? globals.default_voice_id
            : null
        dispatch({
          type: 'LOAD',
          documentId,
          orderedIds: segments.map((s) => s.id),
          sectionStarts: sections.map((s) => s.first_segment_id),
          voice: doc.settings?.voice_id ?? globalVoice ?? voices[0]?.id ?? '',
          speed: doc.settings?.speed ?? globals?.default_speed ?? DEFAULT_SPEED,
        })
        const skip = readSkip(documentId)
        if (skip.footnotes || skip.captions || skip.references) {
          dispatch({ type: 'SET_SKIP', skip, skippedIds: skippedIds(segments, skip) })
        }
        // an unset position arrives as {segment_id: null, offset_ms: 0}
        const pos = doc.position
        if (pos && pos.segment_id != null && segments.some((s) => s.id === pos.segment_id)) {
          dispatch({
            type: 'RESTORE_POSITION',
            segmentId: pos.segment_id,
            offsetMs: pos.offset_ms ?? 0,
          })
          setRestoreId(pos.segment_id)
        }
        setLoaded({ doc, segments, voices })
        void patchDocument(documentId, { opened: true }).catch(() => {})
      },
      (e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      },
    )
    return () => ctrl.abort()
  }, [documentId, dispatch])

  // LIB-2: once the segments are on the page, scroll the restored one into view
  useEffect(() => {
    if (loaded && restoreId !== null) revealSegment(restoreId)
  }, [loaded, restoreId, revealSegment])

  const sections = useMemo(
    () => (loaded ? deriveSections(loaded.doc.sections, loaded.segments) : []),
    [loaded],
  )
  const onSeek = useCallback((id: number, i?: number) => seekTo(id, i), [seekTo])
  const onSkipChange = useCallback(
    (skip: SkipState) => {
      if (!loaded) return
      writeSkip(documentId, skip)
      dispatch({ type: 'SET_SKIP', skip, skippedIds: skippedIds(loaded.segments, skip) })
    },
    [loaded, documentId, dispatch],
  )
  const skippedList = player.state.skippedIds
  const skipped = useMemo(() => new Set(skippedList), [skippedList])

  if (error)
    return (
      <p className="error-box">
        Could not load document {documentId}: {error}
      </p>
    )
  if (!loaded) return <p className="loading">Loading document…</p>
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
          skipped={skipped}
        />
      </div>
      <PlayerBar player={player} voices={loaded.voices} onSkipChange={onSkipChange} />
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
      <main>{m ? <DocView key={m[1]} documentId={Number(m[1])} /> : <Library />}</main>
    </>
  )
}
