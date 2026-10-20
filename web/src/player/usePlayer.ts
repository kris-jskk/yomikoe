// The player hook (spec _agent/specs/m3-reader-interfaces.md §6; D5, D8, D10).
// Owns the AudioContext, the schedule of AudioBufferSourceNodes, prefetch, the rAF highlight loop and
// the D19 instrumentation. M4: position saves (LIB-2), per-document settings saves (LIB-3), the keyboard
// map (PLAY-6), Media Session (PLAY-7) and user skips left out of the schedule (PLAY-8). Reducer state holds no audio objects: they live in a PlayerEngine instance
// created once per hook, and the engine talks back to React only through `dispatch`.

import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react'
import { fetchAudio, patchDocument } from '../api/client'
import type { AudioClip } from '../api/types'
import { keyToAction, stepSpeed } from './keys'
import {
  MediaKeepAlive,
  clearMediaSession,
  setMediaHandlers,
  setMediaMetadata,
  setMediaPlaybackState,
} from './mediaSession'
import { initialState, reduce, type PlayerEvent, type PlayerState } from './machine'
import {
  chainStart,
  findActiveWord,
  followHint,
  centreDistance,
  isScrollKey,
  isSelfScroll,
  locate,
  nextPlayable,
  onFetchFailure,
  mapTimestampsToTokens,
  SELF_SCROLL_MS,
  SELF_SCROLL_SETTLE_PX,
  shouldAutoScroll,
  type FollowHint,
  type MappedTimestamp,
  type ScrollReason,
  type ScheduleEntryView,
  type Token,
} from './schedule'

/** Clips kept decoded or in flight after the one playing (D5: two decoded ahead). */
export const PREFETCH_DEPTH = 2
/** Lead time before a freshly scheduled (non-chained) clip starts, seconds. */
const START_LEAD_SEC = 0.05
/** POSITION is dispatched at most this often (4 Hz). */
const POSITION_MS = 250
/** Entries kept for `window.__hearnarro.entries` per generation. */
const LOG_CAP = 500
/** LIB-2: TICK_SAVE period while playing. */
export const SAVE_TICK_MS = 5_000
/** LIB-3: per-document settings PATCH debounce. */
export const SETTINGS_DEBOUNCE_MS = 500

export interface ScheduleEntry extends ScheduleEntryView {
  /** Null for a zero-length clip: it has an entry (durationSec 0) but nothing plays. */
  source: AudioBufferSourceNode | null
  generation: number
  mapped: MappedTimestamp[]
}

interface Pending {
  key: string
  ctrl: AbortController
  clip: AudioClip | null
  /** Settles once the response has been handled (clip stored or failure dispatched). */
  done?: Promise<void>
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
  /** Follow mode (PLAY-2): false after scroll input in the reading column until a navigation. */
  readonly following: boolean
}

/** `window` with the test hooks (the e2e spec declares the same field globally). */
const hookWindow = () => window as unknown as { __hearnarro?: HearnarroHooks }

export interface Player {
  state: PlayerState
  dispatch: (e: PlayerEvent) => void
  /** Reader registers each segment's element and its tokens (from `tokenize(text)`) on mount. */
  registerSegmentEl: (id: number, el: HTMLElement | null, tokens?: Token[]) => void
  /** Reader registers its reading column: wheel/touchmove inside it stop follow mode. */
  registerReaderEl: (el: HTMLElement | null) => void
  /** True while the advance scrolls the highlighted sentence into view (follow mode, PLAY-2). */
  following: boolean
  /** Where the highlight is while not following: 'up' above the viewport, 'down' below, null in view. */
  followHint: FollowHint
  /** "Back to reading": centre the current segment now and follow again. */
  resumeFollowing: () => void
  /** Play from the current position, or resume (creates the AudioContext inside the gesture). */
  play: () => void
  pause: () => void
  /** Click to seek (PLAY-3): SEEK while active, PLAY from idle/error. */
  seekTo: (segmentId: number, tokenIndex?: number) => void
  lastClip: ClipStats | null
  /** Scroll a segment to the centre without playing (LIB-2 restore). */
  revealSegment: (segmentId: number) => void
  /**
   * TERM-2: a saved pronunciation purged these segments' audio on the server. Drop their prefetched and
   * scheduled clips so the next play requests them again (`PlayerEngine.dropClips`).
   */
  dropClips: (segmentIds: readonly number[]) => void
  /** TERM-2 "Listen": play this sentence from its start (PLAY from idle/error, SEEK otherwise). */
  listen: (segmentId: number) => void
}

type SavedPosition = { segment_id: number; offset_ms: number }

/**
 * LIB-2 position saves: at most one PATCH in flight; a save asked for while one is in flight replaces any
 * queued one and goes out when it settles. A failed save is forgotten (the next tick retries), never shown.
 */
export class PositionSaver {
  private inFlight = false
  private queued: { docId: number; pos: SavedPosition } | null = null
  /** `docId:segment:offset` of the last save sent and not failed. */
  last = ''

  static key(docId: number, pos: SavedPosition) {
    return `${docId}:${pos.segment_id}:${pos.offset_ms}`
  }

  send(docId: number, pos: SavedPosition) {
    if (this.inFlight) {
      this.queued = { docId, pos }
      return
    }
    const k = PositionSaver.key(docId, pos)
    if (k === this.last) return
    this.inFlight = true
    this.last = k
    patchDocument(docId, { position: pos })
      .catch(() => {
        if (this.last === k) this.last = ''
      })
      .finally(() => {
        this.inFlight = false
        const q = this.queued
        this.queued = null
        if (q) this.send(q.docId, q.pos)
      })
  }

  /** pagehide (D26): the last known value with keepalive, unless it is the one already saved. */
  sendBeacon(docId: number, pos: SavedPosition) {
    const k = PositionSaver.key(docId, pos)
    if (k === this.last) return
    this.last = k
    void patchDocument(docId, { position: pos }, { keepalive: true }).catch(() => {})
  }
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
  /** Segments whose prefetch failed this generation; the boundary logic steps over them (PLAY-5). */
  readonly skipped = new Set<number>()
  /** The segment the schedule is blocked on (play/seek target, or the next clip while buffering). */
  targetId: number | null = null
  readonly segEls = new Map<number, HTMLElement>()
  readonly tokens = new Map<number, Token[]>()
  active: { seg: HTMLElement | null; w: HTMLElement | null; key: string } = {
    seg: null,
    w: null,
    key: '',
  }
  lastPos = 0
  /** Follow mode: the advance scrolls only while true; scroll input clears it, navigation sets it. */
  following = true
  hint: FollowHint = null
  /** performance.now() until which page scroll events are the engine's own scrollIntoView. */
  selfScrollUntil = 0
  private selfScrollId: number | null = null
  private selfScrollAt = 0
  private lastDist = Infinity
  private settledCount = 0
  /** Set by an explicit navigation; the next render scrolls to `state.current` with 'navigate'. */
  navPending = false
  private readerEl: HTMLElement | null = null
  private readonly onReaderInput = () => this.noteInput()
  readonly hooks: HearnarroHooks
  private readonly dispatch: (e: PlayerEvent) => void
  private readonly onClip: (s: ClipStats) => void
  private readonly onFollow: (following: boolean, hint: FollowHint) => void

  constructor(
    dispatch: (e: PlayerEvent) => void,
    onClip: (s: ClipStats) => void,
    onFollow: (following: boolean, hint: FollowHint) => void = () => {},
  ) {
    this.dispatch = dispatch
    this.onClip = onClip
    this.onFollow = onFollow
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
    Object.defineProperty(hooks, 'following', { enumerable: true, get: () => this.following })
    this.hooks = hooks as HearnarroHooks
  }

  /** Mirror of the reducer state, synced after every render (layout effect). */
  sync(state: PlayerState) {
    this.state = state
  }

  /** Scroll input in the reading column (or a page-scroll key): stop following. */
  noteInput() {
    this.setFollowing(false)
  }

  /** An explicit navigation was requested: follow again; the next render scrolls to its target. */
  markNavigate() {
    this.navPending = true
    this.setFollowing(true)
  }

  /** "Back to reading": follow again and centre the current segment immediately. */
  resumeFollowing() {
    this.setFollowing(true)
    const id = this.state.current?.segmentId ?? this.startedId
    if (id !== null) this.scrollTo(id, 'navigate')
  }

  setFollowing(f: boolean) {
    if (this.following === f) return
    this.following = f
    this.hint = null
    if (!f) this.computeHint()
    this.onFollow(this.following, this.hint)
  }

  /**
   * A page scroll event (window, capture). Inside the self-scroll window, an event that does not move
   * the target away from the centre is the engine's own scrollIntoView; the window ends early once the
   * target sits within 2 px of centre for two events in a row, and trailing events that keep it there
   * stay the engine's. Any other page scroll (find box, scrollbar, gesture, key) turns follow mode off.
   */
  onPageScroll() {
    const now = performance.now()
    const el = this.selfScrollId !== null ? this.segEls.get(this.selfScrollId) : undefined
    const dist = el ? centreDistance(el.getBoundingClientRect(), window.innerHeight) : Infinity
    if (isSelfScroll(now, this.selfScrollUntil, dist, this.lastDist)) {
      this.lastDist = dist
      if (dist <= SELF_SCROLL_SETTLE_PX) {
        if (++this.settledCount >= 2) this.endSelfScroll()
      } else this.settledCount = 0
      return
    }
    if (this.selfScrollUntil === 0 && dist <= SELF_SCROLL_SETTLE_PX) return // trailing, still centred
    this.endSelfScroll()
    this.selfScrollId = null
    if (this.following) this.setFollowing(false)
    else this.updateHint()
  }

  /** `scrollend` (where supported): ignored in the first 100 ms, which may belong to a replaced scroll. */
  onPageScrollEnd() {
    if (performance.now() - this.selfScrollAt >= 100) this.endSelfScroll()
  }

  /** A settled target or `scrollend`: later scroll events are the reader's. */
  endSelfScroll() {
    this.selfScrollUntil = 0
    this.settledCount = 0
    this.lastDist = Infinity
  }

  /** Recompute the "Back to reading" arrow from the highlighted segment's rect (not following only). */
  updateHint() {
    if (this.following) return
    const before = this.hint
    this.computeHint()
    if (this.hint !== before) this.onFollow(this.following, this.hint)
  }

  private computeHint() {
    const id = this.state.current?.segmentId
    const el = this.active.seg ?? (id !== undefined ? this.segEls.get(id) : undefined) ?? null
    this.hint = followHint(el ? el.getBoundingClientRect() : null, window.innerHeight)
  }

  /** Consume the pending navigation flag. */
  takeNavigate(): boolean {
    const p = this.navPending
    this.navPending = false
    return p
  }

  /** Move the wheel/touchmove listeners to the reading column `el` (null detaches). */
  attachReader(el: HTMLElement | null) {
    if (this.readerEl === el) return
    if (this.readerEl) {
      this.readerEl.removeEventListener('wheel', this.onReaderInput)
      this.readerEl.removeEventListener('touchmove', this.onReaderInput)
    }
    this.readerEl = el
    if (el) {
      el.addEventListener('wheel', this.onReaderInput, { passive: true })
      el.addEventListener('touchmove', this.onReaderInput, { passive: true })
    }
  }

  /** Ids the schedule steps over: failed prefetches (PLAY-5) and the user's skip toggles (PLAY-8). */
  blocked(): ReadonlySet<number> {
    const user = this.state.skippedIds
    if (user.length === 0) return this.skipped
    const out = new Set(user)
    for (const id of this.skipped) out.add(id)
    return out
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

  /**
   * TERM-2: forget the clips of `ids` (their server audio was purged). In-flight or decoded-but-unscheduled
   * clips are aborted and removed. If a dropped clip was still to be heard (pending, or a scheduled entry
   * not yet finished), the schedule is stale: while playing or loading, SEEK to the current position
   * rebuilds it now; otherwise `builtKey` is cleared so the next play() sends PLAY (a rebuild) instead of
   * RESUME, the same path as a voice change while paused. Either way the clips are fetched again.
   */
  dropClips(ids: Iterable<number>) {
    const now = this.ctx?.currentTime ?? 0
    let stale = false
    for (const id of ids) {
      const p = this.pending.get(id)
      if (p) {
        p.ctrl.abort()
        this.pending.delete(id)
        stale = true
      }
      const e = this.entries.get(id)
      if (e && e.startAt + e.durationSec > now) stale = true
    }
    if (!stale) return
    this.builtKey = ''
    const s = this.state
    if ((s.status === 'playing' || s.status === 'loading') && s.current !== null) {
      this.dispatch({ type: 'SEEK', segmentId: s.current.segmentId, offsetMs: s.current.offsetMs })
    }
  }

  private clearSchedule() {
    for (const e of this.entries.values()) if (e.source) stopSource(e.source)
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
    this.skipped.clear()
    this.targetId = s.current.segmentId
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
    // the target plus the next PREFETCH_DEPTH ids the user has not skipped (PLAY-8: never fetched)
    const userSkip = new Set(s.skippedIds)
    const span: number[] = [fromId]
    for (let j = i + 1; j < ids.length && span.length < PREFETCH_DEPTH + 1; j++) {
      if (!userSkip.has(ids[j])) span.push(ids[j])
    }
    const want = new Set(span)
    for (const [id, p] of this.pending) {
      if (!want.has(id)) {
        p.ctrl.abort()
        this.pending.delete(id)
      }
    }
    const k = settingsKey(s.voice, s.speed)
    const [target, ...rest] = span
    this.fetchClip(target, k)
    const head = this.pending.get(target)
    if (!head || head.clip !== null || head.done === undefined) {
      this.prefetch(rest, k) // target decoded or its response already in: prefetch now
      return
    }
    // The server runs GETs on one synthesis thread in arrival order, so a target still in flight is
    // fetched alone and its prefetch starts once its response has arrived (success or failure).
    void head.done.then(() => {
      if (head.ctrl.signal.aborted) return
      if (settingsKey(this.state.voice, this.state.speed) !== k) return
      this.prefetch(rest, k)
    })
  }

  private prefetch(ids: number[], k: string) {
    for (const id of ids) this.fetchClip(id, k)
  }

  /** Start fetching `id` for settings `k` unless it is decoded or already in flight with `k`. */
  private fetchClip(id: number, k: string) {
    const ctx = this.ctx
    const s = this.state
    if (!ctx || this.entries.has(id) || this.skipped.has(id)) return
    const have = this.pending.get(id)
    if (have && have.key === k) return
    have?.ctrl.abort()
    const p: Pending = { key: k, ctrl: new AbortController(), clip: null }
    this.pending.set(id, p)
    p.done = fetchAudio(ctx, id, s.voice, s.speed, p.ctrl.signal).then(
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
        if (onFetchFailure(id, this.targetId) === 'error') {
          this.dispatch({ type: 'FETCH_FAILED', message, generation: this.builtGen })
          return
        }
        // a failed prefetch: skip the segment and keep playing (PLAY-5)
        console.warn('hearnarro:skip-segment', { segmentId: id, reason: message })
        this.skipped.add(id)
        this.scheduleReady()
      },
    )
  }

  /** Start one clip at context time `when`, `offsetSec` into it, and record its entry. */
  private startClip(clip: AudioClip, when: number, offsetSec: number) {
    const ctx = this.ctx!
    const gen = this.builtGen
    // a zero-length clip (PLAY-5) gets an entry of durationSec 0 and no source: the next clip chains
    // at the same startAt
    let source: AudioBufferSourceNode | null = null
    if (clip.buffer !== null) {
      const src = ctx.createBufferSource()
      src.buffer = clip.buffer
      src.playbackRate.value = 1.0 // speed is in the audio (D5)
      src.connect(ctx.destination)
      src.start(when, offsetSec)
      // fallback advance when rAF is throttled (background tab); ignored once the generation moved
      src.onended = () => {
        if (this.builtGen === gen) this.tick()
      }
      source = src
    }
    const entry: ScheduleEntry = {
      segmentId: clip.segmentId,
      source,
      startAt: when - offsetSec,
      durationSec: clip.durationSec, // decoded duration (0 when empty), never X-Duration-Ms
      generation: gen,
      mapped: mapTimestampsToTokens(this.tokens.get(clip.segmentId) ?? [], clip.timestamps),
    }
    this.entries.set(clip.segmentId, entry)
    this.sorted.push(entry)
    if (this.sorted.length > LOG_CAP) this.sorted.shift()
    this.pending.delete(clip.segmentId)
    if (this.hooks.firstStartAt === null) this.hooks.firstStartAt = entry.startAt
    // an empty clip is never located, so no SEGMENT_STARTED moves the window past it: move it here
    if (clip.buffer === null) this.ensureWindow(clip.segmentId)
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
        const offsetSec = Math.min(s.current.offsetMs / 1000, clip.durationSec)
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
      const nextId = nextPlayable(s.orderedIds, tail.segmentId, this.blocked())
      if (nextId === null) return
      const clip = this.pending.get(nextId)?.clip
      if (!clip) return
      // PLAY-5: sample-accurate splice, or a gap when the server was behind
      const { when, gap } = chainStart(tail, ctx.currentTime, this.buffering, START_LEAD_SEC)
      this.startClip(clip, when, 0)
      if (gap && this.buffering) {
        this.buffering = false
        this.dispatch({ type: 'AUDIO_READY', generation: gen, at: performance.now() })
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
      this.active.seg = segEl
      this.updateHint()
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
        this.scrollTo(loc.segmentId, 'advance')
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
    const next = nextPlayable(s.orderedIds, tail.segmentId, this.blocked())
    if (next === null) {
      this.ended = true
      this.dispatch({ type: 'ENDED', offsetMs: Math.round(tail.durationSec * 1000) })
      return
    }
    if (!this.buffering) {
      this.buffering = true
      this.dispatch({ type: 'BUFFERING', generation: gen })
      this.targetId = next // a failure on the clip we now wait for is an error, not a skip
      this.ensureWindow(next)
      this.scheduleReady()
    }
  }

  /** Scroll `segmentId` to the centre: always for 'navigate', only while following for 'advance'. */
  scrollTo(segmentId: number, reason: ScrollReason) {
    const el = this.segEls.get(segmentId)
    if (!el || !shouldAutoScroll(reason, this.following)) return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    this.selfScrollAt = performance.now()
    this.selfScrollUntil = this.selfScrollAt + SELF_SCROLL_MS
    this.selfScrollId = segmentId
    this.settledCount = 0
    this.lastDist = centreDistance(el.getBoundingClientRect(), window.innerHeight)
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

export function usePlayer(opts: { title?: string } = {}): Player {
  const [state, dispatch] = useReducer(reduce, initialState)
  const [lastClip, setLastClip] = useState<ClipStats | null>(null)
  const [follow, setFollow] = useState<{ following: boolean; hint: FollowHint }>({
    following: true,
    hint: null,
  })
  const [engine] = useState(
    () =>
      new PlayerEngine(dispatch, setLastClip, (following, hint) => setFollow({ following, hint })),
  )
  // PLAY-7: one silent looping <audio> keeps the OS media session across a pause (mediaSession.ts)
  const [keepAlive] = useState(() => new MediaKeepAlive())

  useLayoutEffect(() => {
    engine.sync(state)
    // an explicit navigation scrolls to its target at once, before any audio arrives (PLAY-3)
    if (state.current !== null && engine.takeNavigate()) {
      engine.scrollTo(state.current.segmentId, 'navigate')
    }
  }, [engine, state])

  // instrumentation hooks (always set; the gate reads them). Wheel/touchmove are tracked on the reading
  // column (attachReader); keydown stays on window because keyboard page scrolling has no element
  // target, but only scroll keys outside form controls count, so Toc/button keys never stop following.
  // Those listeners stop following before the first scroll event (snappier, and they also catch input
  // during a self-scroll). Any page scroll the engine did not start itself (find box, scrollbar, a
  // gesture the wheel listener misses) stops following too; while not following it refreshes the arrow.
  // Only document scrolls count: an inner scroller such as the Toc list never stops following.
  useEffect(() => {
    const w = hookWindow()
    w.__hearnarro = engine.hooks
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return // a player shortcut (PLAY-6), not a page scroll
      const t = e.target instanceof HTMLElement ? e.target.tagName : null
      if (isScrollKey(e.key, t)) engine.noteInput()
    }
    const isPage = (e: Event) =>
      e.target === document || e.target === document.documentElement || e.target === window
    const onScroll = (e: Event) => {
      if (isPage(e)) engine.onPageScroll()
      else engine.updateHint()
    }
    const onScrollEnd = (e: Event) => {
      if (isPage(e)) engine.onPageScrollEnd()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    window.addEventListener('scrollend', onScrollEnd, { passive: true, capture: true })
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll, { capture: true })
      window.removeEventListener('scrollend', onScrollEnd, { capture: true })
      engine.attachReader(null)
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

  const registerReaderEl = useCallback(
    (el: HTMLElement | null) => engine.attachReader(el),
    [engine],
  )

  // components dispatch through this: a sentence or section skip is an explicit navigation
  const userDispatch = useCallback(
    (e: PlayerEvent) => {
      if (e.type === 'SKIP' || e.type === 'SKIP_SECTION') engine.markNavigate()
      dispatch(e)
    },
    [engine],
  )

  const play = useCallback(() => {
    const s = engine.state
    const ctx = engine.ensureCtx() // inside the click: autoplay policy
    const at = performance.now()
    if (s.status === 'paused' || s.status === 'idle' || s.status === 'error') keepAlive.start()
    if (s.status === 'paused') {
      if (engine.ended) {
        engine.markNavigate()
        dispatch({ type: 'PLAY', at, segmentId: s.orderedIds[0], offsetMs: 0 })
      } else if (settingsKey(s.voice, s.speed) !== engine.builtKey) {
        dispatch({ type: 'PLAY', at }) // voice/speed changed while paused: applies on PLAY (§5)
      } else {
        void ctx.resume()
        dispatch({ type: 'RESUME' })
      }
    } else if (s.status === 'idle' || s.status === 'error') {
      engine.markNavigate() // Play from the saved position scrolls to it
      dispatch({ type: 'PLAY', at })
    }
  }, [engine, keepAlive])

  const pause = useCallback(() => {
    if (engine.state.status !== 'playing') return
    void engine.ctx?.suspend()
    keepAlive.stop()
    dispatch({ type: 'PAUSE' })
  }, [engine, keepAlive])

  const seekTo = useCallback(
    (segmentId: number, tokenIndex?: number) => {
      const offsetMs = tokenIndex === undefined ? 0 : engine.offsetFor(segmentId, tokenIndex)
      const st = engine.state.status
      engine.ensureCtx()
      engine.markNavigate()
      if (st === 'idle' || st === 'error') {
        keepAlive.start() // a word click starts playback: same gesture path as play()
        dispatch({ type: 'PLAY', at: performance.now(), segmentId, offsetMs })
      } else {
        dispatch({ type: 'SEEK', segmentId, offsetMs })
      }
    },
    [engine, keepAlive],
  )

  const resumeFollowing = useCallback(() => engine.resumeFollowing(), [engine])
  const revealSegment = useCallback(
    (segmentId: number) => engine.scrollTo(segmentId, 'navigate'),
    [engine],
  )

  const dropClips = useCallback(
    (segmentIds: readonly number[]) => engine.dropClips(segmentIds),
    [engine],
  )
  const listen = useCallback((segmentId: number) => seekTo(segmentId), [seekTo])

  // LIB-2: TICK_SAVE every 5 s (the reducer ignores it unless playing); a new pendingSave is PATCHed
  const [saver] = useState(() => new PositionSaver())
  useEffect(() => {
    if (!looping) return
    const t = setInterval(() => dispatch({ type: 'TICK_SAVE' }), SAVE_TICK_MS)
    return () => clearInterval(t)
  }, [looping])
  useEffect(() => {
    const docId = engine.state.documentId
    if (state.pendingSave && docId !== null) saver.send(docId, state.pendingSave)
  }, [engine, saver, state.pendingSave])

  // LIB-3: a voice or speed change in the reader PATCHes this document's settings, debounced 500 ms
  const settingsTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sendSettings = useCallback(
    (keepalive: boolean) => {
      const s = engine.state
      if (s.documentId === null) return
      void patchDocument(
        s.documentId,
        { settings: { voice_id: s.voice || null, speed: s.speed } },
        { keepalive },
      ).catch(() => {})
    },
    [engine],
  )
  /** Send a debounced settings save now, if one is waiting. */
  const flushSettings = useCallback(
    (keepalive: boolean) => {
      if (settingsTimer.current === null) return
      clearTimeout(settingsTimer.current)
      settingsTimer.current = null
      sendSettings(keepalive)
    },
    [sendSettings],
  )
  const appDispatch = useCallback(
    (e: PlayerEvent) => {
      userDispatch(e)
      if (e.type === 'SET_VOICE' || e.type === 'SET_SPEED') {
        if (settingsTimer.current !== null) clearTimeout(settingsTimer.current)
        settingsTimer.current = setTimeout(() => {
          settingsTimer.current = null
          sendSettings(false)
        }, SETTINGS_DEBOUNCE_MS)
      }
    },
    [userDispatch, sendSettings],
  )

  // LIB-2: a pause saves where it stopped
  const pauseAndSave = useCallback(() => {
    const s = engine.state
    if (s.status !== 'playing') return
    pause()
    if (s.documentId !== null && s.current !== null) {
      saver.send(s.documentId, { segment_id: s.current.segmentId, offset_ms: s.current.offsetMs })
    }
  }, [engine, pause, saver])

  // D26: pagehide sends the last known position (only once something played) and pending settings
  useEffect(() => {
    const onHide = () => {
      flushSettings(true)
      const s = engine.state
      if (s.documentId === null || s.current === null || saver.last === '') return
      saver.sendBeacon(s.documentId, {
        segment_id: s.current.segmentId,
        offset_ms: s.current.offsetMs,
      })
    }
    window.addEventListener('pagehide', onHide)
    return () => {
      window.removeEventListener('pagehide', onHide)
      flushSettings(false)
    }
  }, [engine, saver, flushSettings])

  // PLAY-6: one keydown listener on the document; form fields keep their keys (keys.ts)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const a = keyToAction({ key: e.key, shiftKey: e.shiftKey, target: e.target })
      if (a === null) return
      if (a.type === 'TOGGLE') {
        // a focused button or link already turns Space into its own click
        const tag = e.target instanceof HTMLElement ? e.target.tagName : ''
        if (tag === 'BUTTON' || tag === 'A') return
        e.preventDefault()
        if (engine.state.status === 'playing') pauseAndSave()
        else play()
        return
      }
      e.preventDefault()
      if (a.type === 'SPEED') {
        appDispatch({ type: 'SET_SPEED', speed: stepSpeed(engine.state.speed, a.delta) })
      } else appDispatch(a)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [engine, play, pauseAndSave, appDispatch])

  // PLAY-7: Media Session (feature-detected in mediaSession.ts)
  useEffect(() => {
    if (opts.title) setMediaMetadata(opts.title)
  }, [opts.title])
  useEffect(() => {
    const off = setMediaHandlers({
      play,
      pause: pauseAndSave,
      previoustrack: () => appDispatch({ type: 'SKIP', by: -1 }),
      nexttrack: () => appDispatch({ type: 'SKIP', by: 1 }),
    })
    return off
  }, [play, pauseAndSave, appDispatch])
  useEffect(
    () => () => {
      keepAlive.dispose()
      clearMediaSession()
    },
    [keepAlive],
  )
  useEffect(() => {
    setMediaPlaybackState(state.status)
    keepAlive.sync(state.status)
  }, [state.status, keepAlive])

  return {
    state,
    dispatch: appDispatch,
    registerSegmentEl,
    registerReaderEl,
    following: follow.following,
    followHint: follow.hint,
    resumeFollowing,
    play,
    pause: pauseAndSave,
    seekTo,
    lastClip,
    revealSegment,
    dropClips,
    listen,
  }
}
