// PLAY-6 keyboard map (spec _agent/specs/m4-library-interfaces.md §2, "Keyboard"); PLAY-10 e/r (m5 §4d). Pure: no DOM access
// beyond reading the event target's tag name and contenteditable flag.

export const SPEED_MIN = 0.5
export const SPEED_MAX = 3.0
export const SPEED_STEP = 0.25

export type KeyAction =
  | { type: 'TOGGLE' }
  | { type: 'SKIP'; by: 1 | -1 }
  | { type: 'SKIP_SECTION'; by: 1 | -1 }
  | { type: 'SPEED'; delta: number }
  | { type: 'SKIP_EQUATION' }
  | { type: 'REPEAT_EQUATION' }

export interface KeyInput {
  key: string
  shiftKey: boolean
  target: EventTarget | null
  /** Modifiers; e and r (PLAY-10) are mapped only without any. Optional so older callers still type-check. */
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
}

const EDITABLE_TAGS = new Set(['INPUT', 'SELECT', 'TEXTAREA'])

/** True when the target is a form field or contenteditable, where keys belong to the field. */
function isEditable(target: EventTarget | null): boolean {
  if (target === null || typeof target !== 'object') return false
  const t = target as { tagName?: unknown; isContentEditable?: unknown }
  if (t.isContentEditable === true) return true
  return typeof t.tagName === 'string' && EDITABLE_TAGS.has(t.tagName.toUpperCase())
}

/** True when no modifier is held (so Ctrl/Cmd+R still reloads the page). */
function noModifier(e: KeyInput): boolean {
  return !e.shiftKey && e.ctrlKey !== true && e.metaKey !== true && e.altKey !== true
}

/** Map a keydown to a player action, or null when unmapped or typed into an editable field. */
export function keyToAction(e: KeyInput): KeyAction | null {
  if (isEditable(e.target)) return null
  switch (e.key) {
    case ' ':
      return { type: 'TOGGLE' }
    case 'ArrowLeft':
      return e.shiftKey ? { type: 'SKIP_SECTION', by: -1 } : { type: 'SKIP', by: -1 }
    case 'ArrowRight':
      return e.shiftKey ? { type: 'SKIP_SECTION', by: 1 } : { type: 'SKIP', by: 1 }
    case '+':
    case '=':
      return { type: 'SPEED', delta: SPEED_STEP }
    case '-':
      return { type: 'SPEED', delta: -SPEED_STEP }
    case 'e':
      return noModifier(e) ? { type: 'SKIP_EQUATION' } : null
    case 'r':
      return noModifier(e) ? { type: 'REPEAT_EQUATION' } : null
    default:
      return null
  }
}

/** speed + delta, clamped to [SPEED_MIN, SPEED_MAX] and rounded to a 0.05 multiple (machine invariant). */
export function stepSpeed(speed: number, delta: number): number {
  const v = Math.round((speed + delta) * 20) / 20
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, v))
}
