// Picker (spec §7; M3 minimum, not LIB-1): the documents from GET /documents; ready ones link to the reader.

import { useEffect, useState } from 'react'
import { getDocuments } from '../api/client'
import type { DocumentSummary } from '../api/types'

export function Picker() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const ctrl = new AbortController()
    getDocuments(ctrl.signal).then(setDocs, (e: unknown) => {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e))
    })
    return () => ctrl.abort()
  }, [])
  if (error) return <p className="error-box">Could not load documents: {error}</p>
  if (docs === null) return <p className="picker">Loading documents…</p>
  return (
    <section className="picker">
      <h2>Documents</h2>
      {docs.length === 0 && <p>No documents yet.</p>}
      <ul>
        {docs.map((d) => (
          <li key={d.id}>
            {d.status === 'ready' ? (
              <a href={`#/doc/${d.id}`}>{d.title || d.filename}</a>
            ) : (
              <span>{d.title || d.filename}</span>
            )}
            <span className="meta">
              {d.page_count} pages · {d.status}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
