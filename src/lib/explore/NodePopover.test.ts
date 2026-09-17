import { describe, expect, it } from 'vitest'
import { NodePopover } from './NodePopover'

describe('node action card placement', () => {
  const card = { width: 320, height: 220 }, desktop = { width: 1280, height: 720 }
  it('stays beside the circle and follows its movement', () => {
    const first = NodePopover.place({ x: 650, y: 360 }, card, desktop, 24, 100, 370)
    const moved = NodePopover.place({ x: 700, y: 400 }, card, desktop, 24, 100, 370)
    expect(first).toEqual({ x: 686, y: 250 })
    expect(moved).toEqual({ x: first.x + 50, y: first.y + 40 })
  })
  it('flips to the left near the right edge', () => {
    const point = NodePopover.place({ x: 1200, y: 400 }, card, desktop, 24, 100, 370)
    expect(point.x + card.width).toBeLessThan(1200)
    expect(point.x).toBeGreaterThanOrEqual(370)
  })
  it.each([{ x: 20, y: 160 }, { x: 370, y: 650 }, { x: -200, y: 1100 }])('keeps a mobile card reachable for anchor %o', anchor => {
    const point = NodePopover.place(anchor, card, { width: 390, height: 740 }, 24, 155)
    expect(point.x).toBeGreaterThanOrEqual(10)
    expect(point.x + card.width).toBeLessThanOrEqual(380)
    expect(point.y).toBeGreaterThanOrEqual(155)
    expect(point.y + card.height).toBeLessThanOrEqual(670)
  })
  it.each([.03, .5, 3])('fits long cards in the visible mobile viewport at graph scale %s', scale => {
    for (const canvas of [{ width: 320, height: 528 }, { width: 667, height: 263 }]) {
      // Simulate a partially visible canvas, including the on-screen keyboard.
      const visible = { x: 0, y: 30, width: canvas.width, height: canvas.height - 90 }
      const bounds = NodePopover.bounds(canvas, 155, 10, visible)
      const oversized = { width: 320, height: 900 }
      for (const anchor of [{ x: -1000 * scale, y: -1000 * scale }, { x: 2000 * scale, y: 3000 * scale }]) {
        const position = NodePopover.place(anchor, oversized, canvas, 24 * scale, 155, 10, visible)
        expect(position.x).toBeGreaterThanOrEqual(visible.x)
        expect(position.y).toBeGreaterThanOrEqual(visible.y)
        expect(position.x + Math.min(oversized.width, bounds.width)).toBeLessThanOrEqual(visible.x + visible.width)
        expect(position.y + Math.min(oversized.height, bounds.height)).toBeLessThanOrEqual(visible.y + visible.height)
      }
    }
  })
})
