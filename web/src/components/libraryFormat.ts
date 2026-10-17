// LIB-1 library table formatting (spec _agent/specs/m4-library-interfaces.md §2, "Library"). Pure.

/** Whole percent, rounded down so 100% means finished; out-of-range and non-finite values clamp. */
export function formatProgress(p: number): string {
  const v = Number.isFinite(p) ? Math.min(1, Math.max(0, p)) : 0
  return `${Math.floor(v * 100 + 1e-9)}%`
}

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

/** Relative "last opened" text; a week or older shows the UTC date YYYY-MM-DD. */
export function formatLastOpened(iso: string | null, now: Date): string {
  if (iso === null) return 'never'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 'never'
  const diff = now.getTime() - t
  if (diff < MIN) return 'just now'
  if (diff < HOUR) return `${Math.floor(diff / MIN)} min ago`
  if (diff < DAY) {
    const h = Math.floor(diff / HOUR)
    return h === 1 ? '1 hour ago' : `${h} hours ago`
  }
  if (diff < 2 * DAY) return 'yesterday'
  if (diff < 7 * DAY) return `${Math.floor(diff / DAY)} days ago`
  return new Date(t).toISOString().slice(0, 10)
}
