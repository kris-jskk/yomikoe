// TERM-2 "Pronounce as" (spec _agent/specs/m5-academic-reading.md §4b "Web"): a respelling for one word,
// saved for this document or for all documents through PUT /pronunciations. The dialog's own state
// (input, scope, error, saved) is local; what plays goes through the player (onListen -> usePlayer.listen,
// which dispatches the existing PLAY / SEEK events), never through an audio element of its own (D5, D10).

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiErrorDetail, putPronunciation } from '../api/client'
import type { PronunciationPut, PronunciationSaved, Segment } from '../api/types'

export type PronounceScope = 'document' | 'global'

export type SubmitResult = { ok: true; saved: PronunciationSaved } | { ok: false; error: string }

/** Save with the chosen scope ('global' sends `document_id: null`); a failure carries the server's message. */
export async function submitPronunciation(
  put: (body: PronunciationPut) => Promise<PronunciationSaved>,
  documentId: number,
  scope: PronounceScope,
  word: string,
  respelling: string,
): Promise<SubmitResult> {
  try {
    const saved = await put({
      document_id: scope === 'document' ? documentId : null,
      word,
      respelling,
    })
    return { ok: true, saved }
  } catch (err) {
    return { ok: false, error: apiErrorDetail(err) }
  }
}

/** The first run of letters/digits (with inner apostrophes) in a selection, or null when there is none. */
export function pickWord(selection: string): string | null {
  const m = /[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/u.exec(selection)
  return m ? m[0] : null
}

/**
 * Ids of the segments whose `normalized_text` holds `word` as a whole token, case-insensitive: the same
 * rule the server uses to purge their cached audio (spec §4b).
 */
export function segmentsWithWord(segments: readonly Segment[], word: string): number[] {
  const esc = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(?<![\\p{L}\\p{N}])${esc}(?![\\p{L}\\p{N}])`, 'iu')
  return segments.filter((s) => re.test(s.normalized_text)).map((s) => s.id)
}

export interface PronounceDialogProps {
  word: string
  documentId: number
  /** After a successful save (the reader drops the invalidated segments' clips). */
  onSaved: (saved: PronunciationSaved) => void
  /** Play the selected sentence through the player. */
  onListen: () => void
  onClose: () => void
  /** Injected for tests; defaults to the API client. */
  put?: (body: PronunciationPut) => Promise<PronunciationSaved>
}

// inline so the dialog floats over the reader without a stylesheet change; system colours follow the theme
const DIALOG_STYLE = {
  position: 'fixed',
  top: '20%',
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 20,
  maxWidth: 'min(28rem, calc(100vw - 32px))',
  padding: '1rem',
  background: 'Canvas',
  color: 'CanvasText',
  border: '1px solid GrayText',
  borderRadius: 8,
  boxShadow: '0 4px 24px rgba(0, 0, 0, 0.25)',
} as const

export function PronounceDialog({
  word,
  documentId,
  onSaved,
  onListen,
  onClose,
  put = putPronunciation,
}: PronounceDialogProps) {
  const [respelling, setRespelling] = useState('')
  const [scope, setScope] = useState<PronounceScope>('document')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<PronunciationSaved | null>(null)
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    input.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(null)
    const r = await submitPronunciation(put, documentId, scope, word, respelling)
    setBusy(false)
    if (r.ok) {
      setSaved(r.saved)
      onSaved(r.saved)
    } else setError(r.error)
  }

  return (
    <div
      className="pronounce-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="Pronounce as"
      style={DIALOG_STYLE}
    >
      <form onSubmit={(e) => void onSubmit(e)}>
        <h2>Pronounce as</h2>
        <p className="pronounce-word">
          <strong>{word}</strong>
        </p>
        <label>
          Respelling{' '}
          <input
            ref={input}
            aria-label="Respelling"
            value={respelling}
            placeholder="e.g. nav-YAY"
            onChange={(e) => {
              setRespelling(e.target.value)
              setSaved(null)
            }}
          />
        </label>
        <fieldset>
          <legend>Apply to</legend>
          <label>
            <input
              type="radio"
              name="pronounce-scope"
              checked={scope === 'document'}
              onChange={() => setScope('document')}
            />{' '}
            this document
          </label>{' '}
          <label>
            <input
              type="radio"
              name="pronounce-scope"
              checked={scope === 'global'}
              onChange={() => setScope('global')}
            />{' '}
            all documents
          </label>
        </fieldset>
        {error !== null && (
          <p className="error-box" role="alert">
            {error}
          </p>
        )}
        <p className="pronounce-status" role="status" aria-live="polite">
          {saved !== null
            ? `Saved; ${saved.invalidated} sentence${saved.invalidated === 1 ? '' : 's'} will be read again`
            : ''}
        </p>
        <div className="pronounce-actions">
          <button type="submit" disabled={busy}>
            Save
          </button>
          <button type="button" disabled={saved === null} onClick={onListen}>
            Listen
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </form>
    </div>
  )
}
