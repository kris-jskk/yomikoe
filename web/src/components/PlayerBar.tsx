// PlayerBar (spec §7, PLAY-1, PLAY-2, PLAY-4): transport, "Back to reading" pill (follow mode),
// voice, speed, status word and D19 stats readout. M4: skip toggles (PLAY-8).
// M5 (spec _agent/specs/m5-academic-reading.md §4d): "Skip equation" / "Repeat equation" (PLAY-10),
// enabled while the current segment is an equation, and the equation-speed select (PLAY-11).

import type { Voice } from '../api/types'
import { BLOCK_FACTOR_MAX, BLOCK_FACTOR_MIN } from '../player/blockSpeed'
import type { PlayerState } from '../player/machine'
import type { SkipState } from '../player/skip'
import type { Player } from '../player/usePlayer'

export interface PlayerBarProps {
  player: Player
  voices: Voice[]
  /** PLAY-8: called with the new toggles; the caller computes the skipped ids and dispatches SET_SKIP. */
  onSkipChange?: (skip: SkipState) => void
}

const SKIP_TOGGLES: { key: keyof SkipState; label: string }[] = [
  { key: 'footnotes', label: 'Skip footnotes' },
  { key: 'captions', label: 'Skip captions' },
  { key: 'references', label: 'Skip references' },
]

const SPEED_MIN = 0.5
const SPEED_MAX = 3
const SPEED_STEP = 0.05

/** Snap a slider value to a 0.05 multiple in [0.5, 3.0]. */
export function snapSpeed(v: number): number {
  const snapped = Math.round(v / SPEED_STEP) * SPEED_STEP
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, Number(snapped.toFixed(2))))
}

const ms = (x: number) => `${Math.round(x)} ms`

/** PLAY-11 select steps: the full 0.05 grid over [BLOCK_FACTOR_MIN, BLOCK_FACTOR_MAX] (11 values). */
export const EQUATION_FACTORS: readonly number[] = Array.from(
  { length: Math.round((BLOCK_FACTOR_MAX - BLOCK_FACTOR_MIN) * 20) + 1 },
  (_, k) => Math.round((BLOCK_FACTOR_MIN + k * 0.05) * 100) / 100,
)

/** PLAY-10: true while the current segment's block type is `equation`. */
export function onEquation(state: PlayerState): boolean {
  if (state.current === null) return false
  const i = state.orderedIds.indexOf(state.current.segmentId)
  return i >= 0 && state.types[i] === 'equation'
}

export function PlayerBar({ player, voices, onSkipChange }: PlayerBarProps) {
  const { state, dispatch, play, pause, lastClip, following, followHint, resumeFollowing } = player
  const playing = state.status === 'playing'
  const eq = onEquation(state)
  const fa = state.firstAudio
  const first =
    fa && fa.startedAt !== null ? `${((fa.startedAt - fa.requestedAt) / 1000).toFixed(2)} s` : '–'
  return (
    <div className="player-bar" role="region" aria-label="Player">
      {!following && (
        <button
          type="button"
          id="follow"
          className="follow"
          aria-label="Back to reading"
          data-hint={followHint ?? 'none'}
          onClick={resumeFollowing}
        >
          Back to reading{followHint === 'up' ? ' ↑' : followHint === 'down' ? ' ↓' : ''}
        </button>
      )}
      <div className="controls">
        <button
          type="button"
          id="prev-section"
          aria-label="Previous section"
          onClick={() => dispatch({ type: 'SKIP_SECTION', by: -1 })}
        >
          ⏮
        </button>
        <button
          type="button"
          id="prev-sentence"
          aria-label="Previous sentence"
          onClick={() => dispatch({ type: 'SKIP', by: -1 })}
        >
          ◀
        </button>
        <button
          type="button"
          id="play-pause"
          className="primary"
          aria-label={playing ? 'Pause' : 'Play'}
          onClick={playing ? pause : play}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <button
          type="button"
          id="next-sentence"
          aria-label="Next sentence"
          onClick={() => dispatch({ type: 'SKIP', by: 1 })}
        >
          ▶
        </button>
        <button
          type="button"
          id="next-section"
          aria-label="Next section"
          onClick={() => dispatch({ type: 'SKIP_SECTION', by: 1 })}
        >
          ⏭
        </button>
        <button
          type="button"
          id="repeat-equation"
          aria-label="Repeat equation"
          title="Repeat equation (r)"
          disabled={!eq}
          onClick={() => dispatch({ type: 'REPEAT_EQUATION' })}
        >
          ↺∑
        </button>
        <button
          type="button"
          id="skip-equation"
          aria-label="Skip equation"
          title="Skip equation (e)"
          disabled={!eq}
          onClick={() => dispatch({ type: 'SKIP_EQUATION' })}
        >
          ∑⇥
        </button>
      </div>
      <select
        id="voice"
        aria-label="Voice"
        value={state.voice}
        onChange={(e) => dispatch({ type: 'SET_VOICE', voice: e.target.value })}
      >
        {voices.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>
      <span className="speed">
        <input
          id="speed"
          type="range"
          min={SPEED_MIN}
          max={SPEED_MAX}
          step={SPEED_STEP}
          aria-label="Speed"
          value={state.speed}
          onChange={(e) =>
            dispatch({ type: 'SET_SPEED', speed: snapSpeed(Number(e.target.value)) })
          }
        />{' '}
        <span id="speed-value">{state.speed.toFixed(2)}x</span>
      </span>
      <label className="equation-speed">
        Equations{' '}
        <select
          id="equation-speed"
          aria-label="Equation playback factor"
          value={state.blockSpeed.equation.toFixed(2)}
          onChange={(e) => dispatch({ type: 'SET_BLOCK_SPEED', equation: Number(e.target.value) })}
        >
          {EQUATION_FACTORS.map((f) => (
            <option key={f} value={f.toFixed(2)}>
              {f.toFixed(2)}x
            </option>
          ))}
        </select>
      </label>
      <span className="skips">
        {SKIP_TOGGLES.map((t) => (
          <label key={t.key}>
            <input
              type="checkbox"
              checked={state.skip[t.key]}
              onChange={(e) => onSkipChange?.({ ...state.skip, [t.key]: e.target.checked })}
            />{' '}
            {t.label}
          </label>
        ))}
      </span>
      <span className="status" role="status" data-status={state.status} aria-live="polite">
        {state.status}
        {state.error ? `: ${state.error}` : ''}
      </span>
      {state.status === 'error' && (
        <>
          <button type="button" id="retry" onClick={() => dispatch({ type: 'RETRY' })}>
            Retry
          </button>
          <button type="button" id="dismiss" onClick={() => dispatch({ type: 'DISMISS' })}>
            Dismiss
          </button>
        </>
      )}
      <span className="stats" id="stats">
        first audio {first} · fetch {lastClip ? ms(lastClip.fetchMs) : '–'} · decode{' '}
        {lastClip ? ms(lastClip.decodeMs) : '–'} · format {lastClip?.mediaType || '–'}
      </span>
    </div>
  )
}
