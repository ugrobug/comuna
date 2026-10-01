import { describe, expect, it } from 'vitest'
import { GallerySwipe } from './GallerySwipe'
const point = (clientX: number, clientY = 0, identifier = 1) => ({ clientX, clientY, identifier })

describe('fullscreen gallery gestures', () => {
  it('moves in either direction once and ignores taps and short drags', () => {
    const gesture = new GallerySwipe()
    for (const [end, expected] of [[20, 1], [180, -1], [110, 0], [100, 0]]) {
      gesture.begin([point(100)], true)
      expect(gesture.finish([point(end)], true)).toBe(expected)
      expect(gesture.finish([point(end)], true)).toBe(0)
    }
  })
  it('keeps vertical scrolling, pinch zoom and zoomed panning out of gallery navigation', () => {
    const gesture = new GallerySwipe()
    gesture.begin([point(100)], true)
    gesture.move([point(95, 80)])
    expect(gesture.finish([point(0, 80)], true)).toBe(0)
    gesture.begin([point(100)], true)
    gesture.move([point(100), point(200, 0, 2)])
    expect(gesture.finish([point(0)], true)).toBe(0)
    gesture.begin([point(100)], false)
    expect(gesture.finish([point(0)], true)).toBe(0)
    gesture.begin([point(100)], true)
    expect(gesture.finish([point(0)], false)).toBe(0)
  })
  it('cancels gestures when the contact changes or the browser cancels the touch', () => {
    const gesture = new GallerySwipe()
    gesture.begin([point(100)], true)
    expect(gesture.finish([point(0, 0, 2)], true)).toBe(0)
    gesture.begin([point(100)], true)
    gesture.cancel()
    expect(gesture.finish([point(0)], true)).toBe(0)
  })
})
