// Library (spec _agent/specs/m4-library-interfaces.md §2, "Library"; LIB-1, LIB-3, LIB-4): the documents
// table, upload with 2 s status polling, delete with an inline confirm, and the global default voice and
// speed (PUT /settings, debounced 500 ms). The defaults never touch an opened document's own settings.

import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  deleteDocument,
  getDocument,
  getDocuments,
  getSettings,
  getVoices,
  putSettings,
  uploadDocument,
} from '../api/client'
import type { DocumentSummary, GlobalSettings, Voice } from '../api/types'
import { formatLastOpened, formatProgress } from './libraryFormat'

/** Upload status poll interval (spec §2). */
export const POLL_MS = 2_000
/** Debounce for PUT /settings. */
const SETTINGS_DEBOUNCE_MS = 500

const done = (status: string) => status === 'ready' || status === 'failed'
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

function Row({
  doc,
  now,
  onDelete,
}: {
  doc: DocumentSummary
  now: Date
  onDelete: (id: number) => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const title = doc.title || doc.filename
  const status =
    doc.status === 'ready' || doc.status === 'failed' || !doc.page_count
      ? doc.status
      : `${doc.status} ${doc.pages_done}/${doc.page_count}`
  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      await onDelete(doc.id)
    } catch (e) {
      setError(errText(e))
      setBusy(false)
      setConfirming(false)
    }
  }
  return (
    <tr data-testid={`doc-row-${doc.id}`}>
      <td>
        {doc.status === 'ready' ? (
          <a href={`#/doc/${doc.id}`} data-testid="doc-title">
            {title}
          </a>
        ) : (
          <span data-testid="doc-title">{title}</span>
        )}
      </td>
      <td data-testid="doc-pages">{doc.page_count}</td>
      <td data-testid="doc-progress">{formatProgress(doc.progress ?? 0)}</td>
      <td data-testid="doc-last-opened">{formatLastOpened(doc.last_opened_at, now)}</td>
      <td data-testid="doc-status">{status}</td>
      <td className="actions">
        {confirming ? (
          <>
            <button type="button" className="danger" disabled={busy} onClick={() => void confirm()}>
              Confirm delete
            </button>{' '}
            <button type="button" disabled={busy} onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirming(true)}>
            Delete
          </button>
        )}
        {error && <span className="row-error"> {error}</span>}
      </td>
    </tr>
  )
}

function Defaults() {
  const [voices, setVoices] = useState<Voice[]>([])
  const [settings, setSettings] = useState<GlobalSettings | null>(null)
  const [speedText, setSpeedText] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    getSettings(ctrl.signal).then(
      (s) => {
        setSettings(s)
        setSpeedText(String(s.default_speed))
      },
      () => {},
    )
    getVoices(ctrl.signal).then(setVoices, () => {})
    return () => ctrl.abort()
  }, [])

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )

  const save = useCallback((next: GlobalSettings) => {
    setSettings(next)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      timer.current = null
      void putSettings(next).catch(() => {})
    }, SETTINGS_DEBOUNCE_MS)
  }, [])

  if (!settings) return null
  const onSpeed = (e: ChangeEvent<HTMLInputElement>) => {
    setSpeedText(e.target.value)
    const v = Number(e.target.value)
    if (e.target.value !== '' && Number.isFinite(v) && v >= 0.5 && v <= 3) {
      save({ ...settings, default_speed: Math.round(v * 20) / 20 })
    }
  }
  return (
    <div className="defaults">
      <label>
        Default voice{' '}
        <select
          value={settings.default_voice_id ?? ''}
          onChange={(e) => save({ ...settings, default_voice_id: e.target.value || null })}
        >
          <option value="">(first available)</option>
          {voices.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Default speed{' '}
        <input type="number" min={0.5} max={3} step={0.05} value={speedText} onChange={onSpeed} />
      </label>
    </div>
  )
}

export function Library() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [polling, setPolling] = useState<number[]>([])
  const [now, setNow] = useState(() => new Date())

  const refresh = useCallback((signal?: AbortSignal) => {
    return getDocuments(signal).then(
      (d) => {
        setDocs(d)
        setNow(new Date())
        setPolling((p) => [
          ...new Set([...p, ...d.filter((x) => !done(x.status)).map((x) => x.id)]),
        ])
      },
      (e: unknown) => {
        if (!signal?.aborted) setError(errText(e))
      },
    )
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    void refresh(ctrl.signal)
    return () => ctrl.abort()
  }, [refresh])

  // poll GET /documents/{id} every 2 s for every document still parsing
  useEffect(() => {
    if (polling.length === 0) return
    const t = setInterval(() => {
      for (const id of polling) {
        getDocument(id).then(
          (d) => {
            setDocs((cur) => (cur ? cur.map((x) => (x.id === id ? { ...x, ...d } : x)) : cur))
            if (done(d.status)) setPolling((p) => p.filter((x) => x !== id))
          },
          () => {},
        )
      }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [polling])

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploadError(null)
    try {
      const r = await uploadDocument(file)
      await refresh()
      if (!done(r.status)) setPolling((p) => (p.includes(r.id) ? p : [...p, r.id]))
    } catch (err) {
      setUploadError(errText(err))
    }
  }

  const onDelete = useCallback(async (id: number) => {
    await deleteDocument(id)
    setDocs((cur) => (cur ? cur.filter((d) => d.id !== id) : cur))
    setPolling((p) => p.filter((x) => x !== id))
  }, [])

  return (
    <section className="library" data-testid="library">
      <div className="library-head">
        <h2>Library</h2>
        <label className="upload">
          Upload PDF{' '}
          <input type="file" accept="application/pdf,.pdf" onChange={(e) => void onUpload(e)} />
        </label>
      </div>
      {uploadError && <p className="error-box">Upload failed: {uploadError}</p>}
      <Defaults />
      {error && <p className="error-box">Could not load documents: {error}</p>}
      {docs === null && !error && <p>Loading documents…</p>}
      {docs !== null && docs.length === 0 && <p>No documents yet.</p>}
      {docs !== null && docs.length > 0 && (
        <table className="doc-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Pages</th>
              <th>Progress</th>
              <th>Last opened</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <Row key={d.id} doc={d} now={now} onDelete={onDelete} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
