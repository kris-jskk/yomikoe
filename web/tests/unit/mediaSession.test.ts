// PLAY-7: the media-key keep-alive element (mediaSession.ts). Pure: the element factory is
// injected, so no DOM is needed (vitest runs in node here).
import { describe, expect, it } from 'vitest'

import {
  MediaKeepAlive,
  silentWavDataUri,
  type KeepAliveMedia,
} from '../../src/player/mediaSession'

class FakeMedia implements KeepAliveMedia {
  loop = false
  src = ''
  paused = true
  plays = 0
  pauses = 0
  removed = false
  play() {
    this.plays++
    this.paused = false
    return Promise.resolve()
  }
  pause() {
    this.pauses++
    this.paused = true
  }
  remove() {
    this.removed = true
  }
}

function setup() {
  const made: FakeMedia[] = []
  const ka = new MediaKeepAlive(() => {
    const m = new FakeMedia()
    m.loop = true
    made.push(m)
    return m
  })
  return { ka, made }
}

describe('PLAY-7 silentWavDataUri', () => {
  it('PLAY-7 is a real-silence 8-bit PCM WAV longer than 5 s', () => {
    const uri = silentWavDataUri()
    expect(uri.startsWith('data:audio/wav;base64,')).toBe(true)
    const bin = atob(uri.slice('data:audio/wav;base64,'.length))
    expect(bin.slice(0, 4)).toBe('RIFF')
    expect(bin.slice(8, 12)).toBe('WAVE')
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0))
    const view = new DataView(bytes.buffer)
    const rate = view.getUint32(24, true)
    const dataLen = view.getUint32(40, true)
    expect(dataLen / rate).toBeGreaterThan(5)
    // unsigned 8-bit PCM: 128 is the zero line, so every sample is silence
    expect(bytes.slice(44).every((b) => b === 128)).toBe(true)
  })
})

describe('PLAY-7 MediaKeepAlive', () => {
  it('PLAY-7 creates nothing until start() (the user-gesture path)', () => {
    const { ka, made } = setup()
    ka.sync('playing')
    ka.sync('paused')
    expect(made).toHaveLength(0)
    expect(ka.element).toBeNull()
  })

  it('PLAY-7 start() creates one looping element and plays it; repeated starts reuse it', () => {
    const { ka, made } = setup()
    ka.start()
    ka.start()
    expect(made).toHaveLength(1)
    expect(made[0].loop).toBe(true)
    expect(made[0].paused).toBe(false)
    expect(made[0].plays).toBe(1)
  })

  it('PLAY-7 sync follows the machine status: paused pauses, playing resumes, idle stops', () => {
    const { ka, made } = setup()
    ka.start()
    ka.sync('paused')
    expect(made[0].paused).toBe(true)
    ka.sync('playing')
    expect(made[0].paused).toBe(false)
    ka.sync('loading')
    expect(made[0].paused).toBe(false)
    ka.sync('idle')
    expect(made[0].paused).toBe(true)
    ka.sync('error')
    expect(made[0].paused).toBe(true)
    expect(made).toHaveLength(1)
  })

  it('PLAY-7 stop() pauses but keeps the element so the page keeps the media session', () => {
    const { ka, made } = setup()
    ka.start()
    ka.stop()
    expect(made[0].paused).toBe(true)
    expect(ka.element).toBe(made[0])
  })

  it('PLAY-7 dispose() pauses, detaches and forgets the element; a later start makes a new one', () => {
    const { ka, made } = setup()
    ka.start()
    ka.dispose()
    expect(made[0].paused).toBe(true)
    expect(made[0].removed).toBe(true)
    expect(ka.element).toBeNull()
    ka.start()
    expect(made).toHaveLength(2)
  })

  it('PLAY-7 a rejected play() (autoplay policy) is swallowed', async () => {
    const ka = new MediaKeepAlive(() => {
      const m = new FakeMedia()
      m.play = () => Promise.reject(new Error('NotAllowedError'))
      return m
    })
    expect(() => ka.start()).not.toThrow()
    await Promise.resolve()
  })

  it('PLAY-7 no factory result (no DOM) makes every call a no-op', () => {
    const ka = new MediaKeepAlive(() => null)
    ka.start()
    ka.sync('playing')
    ka.stop()
    ka.dispose()
    expect(ka.element).toBeNull()
  })
})
