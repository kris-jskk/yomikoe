// The player hook (spec _agent/specs/m3-reader-interfaces.md §6; D5, D8, D10).
// Owns the AudioContext, the schedule of AudioBufferSourceNodes, prefetch, the rAF highlight loop and
// the D19 instrumentation. Reducer state holds no audio objects: they live in a PlayerEngine instance
// created once per hook, and the engine talks back to React only through `dispatch`.

import { useCallback, useEffect, useLayoutEffect, useReducer, useState } from 'react'
import { fetchAudio } from '../api/client'
import type { AudioClip } from '../api/types'
import { initialState, reduce, type PlayerEvent, type PlayerState } from './machine'
import {
  findActiveWord,
  locate,
  mapTimestampsToTokens,
  type MappedTimestamp,
  type ScheduleEntryView,
  type Token,
} from './schedule'

/** Clips kept decoded or in flight after the one playing (D5: two decoded ahead). */
export const PREFETCH_DEPTH = 2
/** Lead time before a freshly scheduled (non-chained) clip starts, seconds. */
const START_LEAD_SEC = 0.05
/** POSITION is dispatched at most this often (4 Hz). */
const POSITION_MS = 250
/** Auto-scroll is suppressed this long after a wheel/touchmove/keydown. */
const SCROLL_COOLDOWN_MS = 3000
/** Entries kept for `window.__hearnarro.entries` per generation. */
const LOG_CAP = 500

export interface ScheduleEntry extends ScheduleEntryView {
  source: AudioBufferSourceNode
  generation: number
  mapped: MappedTimestamp[]
}

interface Pending {
  key: string
  ctrl: AbortController
  clip: AudioClip | null
}

export interface ClipStats {
  fetchMs: number
  decodeMs: number
  mediaType: string
}

/** Test and measurement hooks read by the e2e gate (spec §6 "Instrumentation"). */
export interface HearnarroHooks {
  firstStartAt: number | null
  now: () => number
  readonly entries: ScheduleEntryView[]
}

/** `window` with the test hooks (the e2e spec declares the same field globally). */
const hookWindow = () => window as unknown as { __hearnarro?: HearnarroHooks }

export interface Player {
  state: PlayerState
  dispatch: (e: PlayerEvent) => void
  /** Reader registers each segment's element and its tokens (from `tokenize(text)`) on mount. */
  registerSegmentEl: (id: number, el: HTMLElement | null, tokens?: Token[]) => void
  /** Play from the current position, or resume (creates the AudioContext inside the gesture). */
  play: () => void
  pause: () => void
  /** Click to seek (PLAY-3): SEEK while active, PLAY from idle/error. */
  seekTo: (segmentId: number, tokenIndex?: number) => void
  lastClip: ClipStats | null
}

const settingsKey = (voice: string, speed: number) => `${voice}|${speed.toFixed(2)}`

function stopSource(source: AudioBufferSourceNode) {
  source.onended = null
  try {
    source.stop()
  } catch {
    /* never started or already stopped */
  }
  source.disconnect()
}

/** Everything audio and DOM; not React state. */
export class PlayerEngine {
  state: PlayerState = initialState
  ctx: AudioContext | null = null
  /** Scheduled sources of the current generation, by segment id. */
  readonly entries = new Map<number, ScheduleEntry>()
  /** The same entries sorted by startAt (chaining is monotonic); `locate` reads this. */
  sorted: ScheduleEntry[] = []
  /** Fetches in flight or decoded and not yet scheduled, by segment id; each has its AbortController. */
  readonly pending = new Map<number, Pending>()
  builtGen = -1
  builtKey = ''
  buffering = false
  ended = false
  startedId: number | null = null
  readonly segEls = new Map<number, HTMLElement>()
  readonly tokens = new Map<number, Token[]>()
  active: { seg: HTMLElement | null; w: HTMLElement | null; key: string } = {
    seg: null,
    w: null,
    key: '',
  }
  lastPos = 0
  lastInput = -Infinity
  readonly hooks: HearnarroHooks
  private readonly dispatch: (e: PlayerEvent) => void
  private readonly onClip: (s: ClipStats) => void

  constructor(dispatch: (e: PlayerEvent) => void, onClip: (s: ClipStats) => void) {
    this.dispatch = dispatch
    this.onClip = onClip
    const hooks = { firstStartAt: null, now: () => this.ctx?.currentTime ?? 0 }
    Object.defineProperty(hooks, 'entries', {
      enumerable: true,
      get: () =>
        this.sorted.map((e) => ({
          segmentId: e.segmentId,
          startAt: e.startAt,
          durationSec: e.durationSec,
        })),
    })
    this.hooks = hooks as HearnarroHooks
  }

  /** Mirror of the reducer state, synced after every render (layout effect). */
  sync(state: PlayerState) {
    this.state = state
  }

  noteInput() {
    this.lastInput = performance.now()
  }

  ensureCtx(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext()
    if (this.ctx.state === 'suspended') void this.ctx.resume()
    return this.ctx
  }

  dispose() {
    this.clearSchedule()
    for (const p of this.pending.values()) p.ctrl.abort()
    this.pending.clear()
    const ctx = this.ctx
    this.ctx = null
    this.builtGen = -1
    if (ctx) void ctx.close()
  }

  private clearSchedule() {
    for (const e of this.entries.values()) stopSource(e.source)
    this.entries.clear()
    this.sorted = []
  }

  /** On entering `loading` with a new generation: drop the schedule and fetch the target window. */
  build(s: PlayerState) {
    if (s.current === null) return
    this.ensureCtx()
    this.builtGen = s.generation
    this.builtKey = settingsKey(s.voice, s.speed)
    this.buffering = false
    this.ended = false
    this.startedId = null
    this.clearSchedule()
    this.ensureWindow(s.current.segmentId)
    this.scheduleReady()
  }

  /** Keep [fromId, fromId + PREFETCH_DEPTH] fetched or in flight; abort clips outside it. */
  ensureWindow(fromId: number) {
    const ctx = this.ctx
    const s = this.state
    if (!ctx) return
    const ids = s.orderedIds
    const i = ids.indexOf(fromId)
    if (i < 0) return
    const want = new Set(ids.slice(i, i + PREFETCH_DEPTH + 1))
    for (const [id, p] of this.pending) {
      if (!want.has(id)) {
        p.ctrl.abort()
        this.pending.delete(id)
      }
    }
    const k = settingsKey(s.voice, s.speed)
    for (const id of want) {
      if (this.entries.has(id)) continue
      const have = this.pending.get(id)
      if (have && have.key === k) continue
      have?.ctrl.abort()
      const p: Pending = { key: k, ctrl: new AbortController(), clip: null }
      this.pending.set(id, p)
      fetchAudio(ctx, id, s.voice, s.speed, p.ctrl.signal).then(
        (clip) => {
          if (this.pending.get(id) !== p) return
          p.clip = clip
          this.onClip({ fetchMs: clip.fetchMs, decodeMs: clip.decodeMs, mediaType: clip.mediaType })
          // a clip kept across a rebuild (same id, voice, speed) serves the new generation too;
          // scheduleReady itself checks the generation against the reducer's
          this.scheduleReady()
        },
        (err: unknown) => {
          if (this.pending.get(id) !== p || p.ctrl.signal.aborted) return
          this.pending.delete(id)
          const message = err instanceof Error ? err.message : String(err)
          this.dispatch({ type: 'FETCH_FAILED', message, generation: this.builtGen })
        },
      )
    }
  }

  /** Start one clip at context time `when`, `offsetSec` into it, and record its entry. */
  private startClip(clip: AudioClip, when: number, offsetSec: number) {
    const ctx = this.ctx!
    const gen = this.builtGen
    const source = ctx.createBufferSource()
    source.buffer = clip.buffer
    source.playbackRate.value = 1.0 // speed is in the audio (D5)
    source.connect(ctx.destination)
    source.start(when, offsetSec)
    const entry: ScheduleEntry = {
      segmentId: clip.segmentId,
      source,
      startAt: when - offsetSec,
      durationSec: clip.buffer.duration, // decoded duration, never X-Duration-Ms
      generation: gen,
      mapped: mapTimestampsToTokens(this.tokens.get(clip.segmentId) ?? [], clip.timestamps),
    }
    // fallback advance when rAF is throttled (background tab); ignored once the generation moved
    source.onended = () => {
      if (this.builtGen === gen) this.tick()
    }
    this.entries.set(clip.segmentId, entry)
    this.sorted.push(entry)
    if (this.sorted.length > LOG_CAP) this.sorted.shift()
    this.pending.delete(clip.segmentId)
    if (this.hooks.firstStartAt === null) this.hooks.firstStartAt = entry.startAt
    return entry
  }

  /** Schedule every decoded clip that can be placed now: the first one, chained ones, or after buffering. */
  scheduleReady() {
    const ctx = this.ctx
    const s = this.state
    if (!ctx || s.current === null || s.generation !== this.builtGen) return
    const gen = this.builtGen
    for (;;) {
      const tail = this.sorted.length > 0 ? this.sorted[this.sorted.length - 1] : null
      if (tail === null) {
        const clip = this.pending.get(s.current.segmentId)?.clip
        if (!clip) return
        const offsetSec = Math.min(s.current.offsetMs / 1000, clip.buffer.duration)
        const first = this.startClip(clip, ctx.currentTime + START_LEAD_SEC, offsetSec)
        // show the target word now, so the DOM agrees with `playing` during the 50 ms lead
        this.highlight(first.segmentId, findActiveWord(first.mapped, offsetSec * 1000) ?? 0)
        const at = performance.now()
        const fa = s.firstAudio
        if (fa && fa.startedAt === null) {
          const toks = this.tokens.get(clip.segmentId) ?? []
          console.info('hearnarro:first-audio', {
            ms: Math.round(at - fa.requestedAt),
            speed: s.speed,
            voice: s.voice,
            segmentId: clip.segmentId,
            textLength: toks.length ? toks[toks.length - 1].charEnd : 0,
          })
        }
        this.dispatch({ type: 'AUDIO_READY', generation: gen, at })
        continue
      }
      const ids = s.orderedIds
      const nextId = ids[ids.indexOf(tail.segmentId) + 1]
      if (nextId === undefined) return
      const clip = this.pending.get(nextId)?.clip
      if (!clip) return
      const end = tail.startAt + tail.durationSec
      if (!this.buffering && end > ctx.currentTime) {
        this.startClip(clip, end, 0) // PLAY-5: sample-accurate splice
      } else {
        this.startClip(clip, ctx.currentTime + START_LEAD_SEC, 0) // a gap: the server was behind
        if (this.buffering) {
          this.buffering = false
          this.dispatch({ type: 'AUDIO_READY', generation: gen, at: performance.now() })
        }
      }
    }
  }

  /**
   * The hot path (D8): move the highlight to (segmentId, tokenIndex) by toggling classes on element
   * refs. No React state is read or written here.
   */
  highlight(segmentId: number, tokenIndex: number | null) {
    const a = this.active
    const k = `${segmentId}:${tokenIndex}`
    if (a.key === k) return
    const segEl = this.segEls.get(segmentId) ?? null
    if (a.seg !== segEl) {
      if (a.seg) {
        a.seg.classList.remove('active')
        delete a.seg.dataset.active
      }
      if (segEl) {
        segEl.classList.add('active')
        segEl.dataset.active = 'true'
      }
    }
    const w =
      segEl && tokenIndex !== null
        ? segEl.querySelector<HTMLElement>(`.w[data-i="${tokenIndex}"]`)
        : null
    if (a.w !== w) {
      a.w?.classList.remove('active')
      w?.classList.add('active')
    }
    this.active = { seg: segEl, w, key: k }
  }

  /** One rAF frame: highlight; on a segment change SEGMENT_STARTED, prefetch, scroll; boundaries. */
  tick() {
    const ctx = this.ctx
    const s = this.state
    if (!ctx) return
    const gen = this.builtGen
    const now = ctx.currentTime
    const loc = locate(this.sorted, now)
    if (loc) {
      const entry = this.entries.get(loc.segmentId)
      let ti = entry ? findActiveWord(entry.mapped, loc.elapsedMs) : null
      // before the first timestamp the segment has started: show its first token
      if (ti === null && (this.tokens.get(loc.segmentId)?.length ?? 0) > 0) ti = 0
      this.highlight(loc.segmentId, ti)
      if (this.startedId !== loc.segmentId) {
        this.startedId = loc.segmentId
        if (s.status === 'playing') {
          this.dispatch({ type: 'SEGMENT_STARTED', segmentId: loc.segmentId, generation: gen })
        }
        this.ensureWindow(loc.segmentId)
        this.scheduleReady()
        this.autoScroll(loc.segmentId)
      }
      const t = performance.now()
      if (s.status === 'playing' && t - this.lastPos >= POSITION_MS) {
        this.lastPos = t
        this.dispatch({
          type: 'POSITION',
          segmentId: loc.segmentId,
          offsetMs: Math.round(loc.elapsedMs),
        })
      }
      return
    }
    const tail = this.sorted.length > 0 ? this.sorted[this.sorted.length - 1] : null
    if (s.status !== 'playing' || tail === null || now < tail.startAt + tail.durationSec) return
    const ids = s.orderedIds
    const idx = ids.indexOf(tail.segmentId)
    if (idx === ids.length - 1) {
      this.ended = true
      this.dispatch({ type: 'ENDED', offsetMs: Math.round(tail.durationSec * 1000) })
      return
    }
    if (!this.buffering) {
      this.buffering = true
      this.dispatch({ type: 'BUFFERING', generation: gen })
      this.ensureWindow(ids[idx + 1])
      this.scheduleReady()
    }
  }

  private autoScroll(segmentId: number) {
    const el = this.segEls.get(segmentId)
    if (!el || performance.now() - this.lastInput <= SCROLL_COOLDOWN_MS) return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' })
  }

  /** Token click offset: start_ms of the token's first mapped timestamp if the clip is known, else 0. */
  offsetFor(segmentId: number, tokenIndex: number): number {
    const entry = this.entries.get(segmentId)
    const pend = this.pending.get(segmentId)?.clip
    const mapped =
      entry?.mapped ??
      (pend ? mapTimestampsToTokens(this.tokens.get(segmentId) ?? [], pend.timestamps) : [])
    return mapped.find((x) => x.tokenIndex === tokenIndex)?.start_ms ?? 0
  }
}

export function usePlayer(): Player {
  const [state, dispatch] = useReducer(reduce, initialState)
  const [lastClip, setLastClip] = useState<ClipStats | null>(null)
  const [engine] = useState(() => new PlayerEngine(dispatch, setLastClip))

  useLayoutEffect(() => {
    engine.sync(state)
  }, [engine, state])

  // instrumentation hooks (always set; the gate reads them) and user-input tracking for auto-scroll
  useEffect(() => {
    const w = hookWindow()
    w.__hearnarro = engine.hooks
    const onInput = () => engine.noteInput()
    window.addEventListener('wheel', onInput, { passive: true })
    window.addEventListener('touchmove', onInput, { passive: true })
    window.addEventListener('keydown', onInput)
    return () => {
      window.removeEventListener('wheel', onInput)
      window.removeEventListener('touchmove', onInput)
      window.removeEventListener('keydown', onInput)
      engine.dispose()
      if (w.__hearnarro === engine.hooks) delete w.__hearnarro
    }
  }, [engine])

  // schedule build on every new generation in `loading` (BUFFERING keeps the generation: no rebuild)
  useEffect(() => {
    if (state.status === 'loading' && state.generation !== engine.builtGen) engine.build(state)
  }, [engine, state])

  // rAF loop while playing, and while loading so a buffering schedule keeps highlighting
  const looping = state.status === 'playing' || state.status === 'loading'
  useEffect(() => {
    if (!looping) return
    let raf = 0
    const frame = () => {
      engine.tick()
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [engine, looping])

  const registerSegmentEl = useCallback(
    (id: number, el: HTMLElement | null, tokens?: Token[]) => {
      if (el) {
        engine.segEls.set(id, el)
        if (tokens) engine.tokens.set(id, tokens)
      } else {
        engine.segEls.delete(id)
      }
    },
    [engine],
  )

  const play = useCallback(() => {
    const s = engine.state
    const ctx = engine.ensureCtx() // inside the click: autoplay policy
    const at = performance.now()
    if (s.status === 'paused') {
      if (engine.ended) {
        dispatch({ type: 'PLAY', at, segmentId: s.orderedIds[0], offsetMs: 0 })
      } else if (settingsKey(s.voice, s.speed) !== engine.builtKey) {
        dispatch({ type: 'PLAY', at }) // voice/speed changed while paused: applies on PLAY (§5)
      } else {
        void ctx.resume()
        dispatch({ type: 'RESUME' })
      }
    } else if (s.status === 'idle' || s.status === 'error') {
      dispatch({ type: 'PLAY', at })
    }
  }, [engine])

  const pause = useCallback(() => {
    if (engine.state.status !== 'playing') return
    void engine.ctx?.suspend()
    dispatch({ type: 'PAUSE' })
  }, [engine])

  const seekTo = useCallback(
    (segmentId: number, tokenIndex?: number) => {
      const offsetMs = tokenIndex === undefined ? 0 : engine.offsetFor(segmentId, tokenIndex)
      const st = engine.state.status
      engine.ensureCtx()
      if (st === 'idle' || st === 'error') {
        dispatch({ type: 'PLAY', at: performance.now(), segmentId, offsetMs })
      } else {
        dispatch({ type: 'SEEK', segmentId, offsetMs })
      }
    },
    [engine],
  )

  return { state, dispatch, registerSegmentEl, play, pause, seekTo, lastClip }
}
