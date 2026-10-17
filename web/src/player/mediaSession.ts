// PLAY-7 Media Session (spec _agent/specs/m4-library-interfaces.md §2, "Media Session"). A thin,
// feature-detected wrapper over navigator.mediaSession: every call is a no-op where it is missing.

export interface MediaHandlers {
  play: () => void
  pause: () => void
  previoustrack: () => void
  nexttrack: () => void
}

const ACTIONS = ['play', 'pause', 'previoustrack', 'nexttrack'] as const

function session(): MediaSession | null {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return null
  return navigator.mediaSession ?? null
}

/** Title = document title, artist "HearNarro". */
export function setMediaMetadata(title: string): void {
  const ms = session()
  if (!ms || typeof MediaMetadata === 'undefined') return
  try {
    ms.metadata = new MediaMetadata({ title, artist: 'HearNarro' })
  } catch {
    /* unsupported */
  }
}

/** Install the four handlers; returns a cleanup that removes them. */
export function setMediaHandlers(h: MediaHandlers): () => void {
  const ms = session()
  if (!ms) return () => {}
  for (const a of ACTIONS) {
    try {
      ms.setActionHandler(a, () => h[a]())
    } catch {
      /* action not supported by this browser */
    }
  }
  return () => {
    for (const a of ACTIONS) {
      try {
        ms.setActionHandler(a, null)
      } catch {
        /* ignore */
      }
    }
  }
}

/** Mirror the machine: playing/loading -> 'playing', paused -> 'paused', otherwise 'none'. */
export function setMediaPlaybackState(status: string): void {
  const ms = session()
  if (!ms) return
  ms.playbackState =
    status === 'playing' || status === 'loading'
      ? 'playing'
      : status === 'paused'
        ? 'paused'
        : 'none'
}

/** Clear metadata and state when the reader closes. */
export function clearMediaSession(): void {
  const ms = session()
  if (!ms) return
  ms.metadata = null
  ms.playbackState = 'none'
}
