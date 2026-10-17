// PLAY-6: keyboard map (spec _agent/specs/m4-library-interfaces.md §2, "Keyboard"). Pure: no DOM needed.
import { describe, expect, it } from 'vitest'

import { SPEED_MAX, SPEED_MIN, SPEED_STEP, keyToAction, stepSpeed } from '../../src/player/keys'

type Target = { tagName?: string; isContentEditable?: boolean } | null

function key(k: string, shiftKey = false, target: Target = { tagName: 'BODY' }) {
  return { key: k, shiftKey, target: target as unknown as EventTarget | null }
}

describe('PLAY-6 keyToAction', () => {
  it('PLAY-6 Space toggles play/pause', () => {
    expect(keyToAction(key(' '))).toEqual({ type: 'TOGGLE' })
  })

  it('PLAY-6 ArrowLeft/ArrowRight skip one sentence', () => {
    expect(keyToAction(key('ArrowLeft'))).toEqual({ type: 'SKIP', by: -1 })
    expect(keyToAction(key('ArrowRight'))).toEqual({ type: 'SKIP', by: 1 })
  })

  it('PLAY-6 Shift+ArrowLeft/Shift+ArrowRight skip one section', () => {
    expect(keyToAction(key('ArrowLeft', true))).toEqual({ type: 'SKIP_SECTION', by: -1 })
    expect(keyToAction(key('ArrowRight', true))).toEqual({ type: 'SKIP_SECTION', by: 1 })
  })

  it('PLAY-6 + and = step speed up, - steps it down', () => {
    expect(keyToAction(key('+', true))).toEqual({ type: 'SPEED', delta: 0.25 })
    expect(keyToAction(key('='))).toEqual({ type: 'SPEED', delta: 0.25 })
    expect(keyToAction(key('-'))).toEqual({ type: 'SPEED', delta: -0.25 })
  })

  it('PLAY-6 unmapped keys return null', () => {
    for (const k of ['a', 'Enter', 'ArrowUp', 'ArrowDown', 'Tab', 'Escape']) {
      expect(keyToAction(key(k))).toBeNull()
    }
  })

  it.each([
    ['INPUT', { tagName: 'INPUT' }],
    ['SELECT', { tagName: 'SELECT' }],
    ['TEXTAREA', { tagName: 'TEXTAREA' }],
    ['lower-case input', { tagName: 'input' }],
    ['contenteditable', { tagName: 'DIV', isContentEditable: true }],
  ])('PLAY-6 keys are ignored when the target is %s', (_name, target) => {
    for (const k of [' ', 'ArrowLeft', 'ArrowRight', '+', '=', '-']) {
      expect(keyToAction(key(k, false, target))).toBeNull()
    }
  })

  it('PLAY-6 a null target is not an editable field', () => {
    expect(keyToAction(key(' ', false, null))).toEqual({ type: 'TOGGLE' })
  })
})

describe('PLAY-6 stepSpeed', () => {
  it('PLAY-6 speed bounds and step match the spec', () => {
    expect(SPEED_MIN).toBe(0.5)
    expect(SPEED_MAX).toBe(3.0)
    expect(SPEED_STEP).toBe(0.25)
  })

  it('PLAY-6 steps by 0.25 and clamps to [0.5, 3.0]', () => {
    expect(stepSpeed(1.25, 0.25)).toBe(1.5)
    expect(stepSpeed(1.25, -0.25)).toBe(1.0)
    expect(stepSpeed(2.9, 0.25)).toBe(3.0)
    expect(stepSpeed(3.0, 0.25)).toBe(3.0)
    expect(stepSpeed(0.6, -0.25)).toBe(0.5)
    expect(stepSpeed(0.5, -0.25)).toBe(0.5)
  })

  it('PLAY-6 result stays a 0.05 multiple (machine speed invariant)', () => {
    const s = stepSpeed(1.1, 0.25)
    expect(Math.round(s * 100) % 5).toBe(0)
    expect(s).toBeCloseTo(1.35, 10)
  })
})
