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

// PLAY-7 media-key keep-alive. Playback is Web Audio only (D5) and pause suspends the AudioContext
// (D24), so after a pause nothing on the page is playing media and the OS media session (macOS
// Now Playing, F8 / Touch Bar) is released: the next hardware "play" never reaches our handler.
// One hidden, looping <audio> element of real silence is played while the machine plays and
// paused (not removed) while it is paused, so a paused media element keeps the page as the
// session owner. It is one element for the whole player and carries no speech: D5 still holds
// (no per-segment <audio>, no MSE).

/** The subset of HTMLAudioElement the keep-alive uses (injectable for tests). */
export interface KeepAliveMedia {
  loop: boolean
  src: string
  readonly paused: boolean
  play(): Promise<void> | void
  pause(): void
  remove?(): void
}

/** A WAV of real silence: unsigned 8-bit PCM mono, every sample 128. Longer than 5 s because
 * browsers ignore very short media for media-session purposes. */
export function silentWavDataUri(seconds = 6, rate = 8000): string {
  const n = Math.round(seconds * rate)
  const buf = new Uint8Array(44 + n)
  const v = new DataView(buf.buffer)
  const ascii = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) buf[o + i] = s.charCodeAt(i)
  }
  ascii(0, 'RIFF')
  v.setUint32(4, 36 + n, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  v.setUint32(16, 16, true) // fmt chunk size
  v.setUint16(20, 1, true) // PCM
  v.setUint16(22, 1, true) // mono
  v.setUint32(24, rate, true)
  v.setUint32(28, rate, true) // byte rate
  v.setUint16(32, 1, true) // block align
  v.setUint16(34, 8, true) // bits per sample
  ascii(36, 'data')
  v.setUint32(40, n, true)
  buf.fill(128, 44)
  let bin = ''
  for (let i = 0; i < buf.length; i += 0x8000) {
    bin += String.fromCharCode(...buf.subarray(i, i + 0x8000))
  }
  return `data:audio/wav;base64,${btoa(bin)}`
}

/** Marker attribute; the e2e probe finds the element by it. */
export const KEEPALIVE_ATTR = 'data-hearnarro-keepalive'

function makeSilentAudio(): KeepAliveMedia | null {
  if (typeof document === 'undefined' || !document.body) return null
  const el = document.createElement('audio')
  el.loop = true
  el.preload = 'auto'
  el.hidden = true
  el.setAttribute(KEEPALIVE_ATTR, '')
  el.setAttribute('aria-hidden', 'true')
  el.src = silentWavDataUri()
  document.body.appendChild(el)
  return el
}

export class MediaKeepAlive {
  element: KeepAliveMedia | null = null
  private readonly make: () => KeepAliveMedia | null

  constructor(make: () => KeepAliveMedia | null = makeSilentAudio) {
    this.make = make
  }

  /** Call from the user-gesture path (click, key, media-session action): creates lazily, plays. */
  start(): void {
    if (!this.element) this.element = this.make()
    this.playEl()
  }

  /** Pause, keeping the element so the page stays the media-session owner. */
  stop(): void {
    if (this.element && !this.element.paused) this.element.pause()
  }

  /** Mirror the machine status; never creates the element (that needs a user gesture). */
  sync(status: string): void {
    if (!this.element) return
    if (status === 'playing' || status === 'loading') this.playEl()
    else this.stop()
  }

  /** Unmount: pause, detach, forget. */
  dispose(): void {
    const el = this.element
    if (!el) return
    this.element = null
    el.pause()
    el.remove?.()
  }

  private playEl(): void {
    const el = this.element
    if (!el || !el.paused) return
    try {
      const p = el.play()
      if (p) p.catch(() => {})
    } catch {
      /* autoplay policy or unsupported: playback itself is unaffected */
    }
  }
}
