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
})
