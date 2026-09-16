import { describe, expect, it } from 'vitest'
import { GraphDrag } from './GraphDrag'
import type { GraphPoint } from './GraphLayout'

const points = (): GraphPoint[] => Array.from({ length: 5 }, (_, index) => ({ id: index + 1, x: index * 80, y: index * 30, width: 64, height: 80, anchorY: 28, fixed: false }))
const edges = [
  { id: 1, source: 1, target: 2 },
  { id: 2, source: 3, target: 1 },
  { id: 3, source: 2, target: 4 },
  { id: 4, source: 4, target: 3 },
]
const distance = (a: GraphPoint, b: GraphPoint) => Math.hypot(a.x - b.x, a.y - b.y)

describe('spring following while dragging an interest', () => {
  it('moves the grabbed node immediately while direct neighbors follow gradually', () => {
    const before = points(), drag = new GraphDrag({ id: 1, kind: 'element' }, edges, before)
    const moved = drag.move(before, -100, 40)
    expect(moved[0]).toMatchObject({ x: -100, y: 40, fixed: true })
    expect(moved[1]).toBe(before[1])
    expect(moved[2]).toBe(before[2])
    const frame = drag.step(moved, 1 / 60)
    expect(frame.moving).toBe(true)
    for (const index of [1, 2]) {
      expect(frame.points[index].x).toBeLessThan(before[index].x)
      expect(frame.points[index].x).toBeGreaterThan(before[index].x - 10)
      expect(frame.points[index].fixed).toBe(true)
    }
    expect(frame.points[3]).toBe(before[3])
    expect(frame.points[4]).toBe(before[4])
    expect(before.every(point => !point.fixed)).toBe(true)
  })
  it('allows springs to stretch, overshoot and settle after release without preserving rigid offsets', () => {
    const before = points().map(p => ({ ...p, width: 32, height: 32, anchorY: 16 })), drag = new GraphDrag({ id: 1, kind: 'element' }, edges, before)
    let current = drag.move(before, -100, 40), moving = true, crossedRestLength = false
    const restLength = distance(before[0], before[1])
    expect(distance(current[0], current[1])).toBeGreaterThan(restLength)
    for (let i = 0; i < 600 && moving; i++) {
      const frame = drag.step(current, 1 / 60)
      current = frame.points; moving = frame.moving
      if (distance(current[0], current[1]) < restLength - 1) crossedRestLength = true
    }
    expect(crossedRestLength).toBe(true)
    expect(moving).toBe(false)
    expect(Math.abs(distance(current[0], current[1]) - restLength)).toBeLessThan(0.2)
    expect(Math.abs(current[1].x - (before[1].x - 100))).toBeGreaterThan(1)
    expect(current[0]).toMatchObject({ x: -100, y: 40 })
    expect(current[3]).toBe(before[3])
  })
  it('is stable across refresh rates, duplicate links, cycles and long frame gaps', () => {
    const before = points()
    const normal = new GraphDrag({ id: 1, kind: 'element' }, edges, before)
    const duplicate = new GraphDrag({ id: 1, kind: 'element' }, [...edges, { id: 5, source: 2, target: 1 }, { id: 6, source: 1, target: 1 }], before)
    let a = normal.move(before, -100, 40), b = duplicate.move(before, -100, 40)
    for (let i = 0; i < 60; i++) a = normal.step(a, 1 / 60).points
    for (let i = 0; i < 120; i++) b = duplicate.step(b, 1 / 120).points
    for (let i = 0; i < a.length; i++) {
      expect(a[i].x).toBeCloseTo(b[i].x, 6)
      expect(a[i].y).toBeCloseTo(b[i].y, 6)
    }
    expect(duplicate.step(b, 60).points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
  })
  it('lets communities and isolated interests move individually', () => {
    for (const node of [{ id: 2, kind: 'community' }, { id: 5, kind: 'element' }] as const) {
      const before = points(), drag = new GraphDrag(node, edges, before)
      const result = drag.step(drag.move(before, -20, 30), 1 / 60)
      expect(result.moving).toBe(false)
      expect(result.points.filter(p => p.fixed).map(p => p.id)).toEqual([node.id])
    }
  })
  it('handles filtered-out and coincident neighbors without creating nodes or non-finite positions', () => {
    const before = points().slice(0, 2).map(p => ({ ...p, x: 0, y: 0 }))
    const drag = new GraphDrag({ id: 1, kind: 'element' }, edges, before)
    const result = drag.step(drag.move(before, 20, 30), 1 / 60)
    expect(result.points).toHaveLength(2)
    expect(result.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
    expect(drag.step([], 1 / 60)).toEqual({ points: [], moving: false })
  })
})

function expectFollowersSeparated(current: GraphPoint[], followers: Set<number>) {
  for (let i = 0; i < current.length; i++) for (let j = i + 1; j < current.length; j++) {
    const a = current[i], b = current[j]
    if (!followers.has(a.id) && !followers.has(b.id)) continue
    const leftA = a.x - a.width / 2, leftB = b.x - b.width / 2
    const topA = a.y - a.anchorY, topB = b.y - b.anchorY
    expect(leftA + a.width <= leftB || leftB + b.width <= leftA || topA + a.height <= topB || topB + b.height <= topA).toBe(true)
  }
}

describe('followers spreading after a drag', () => {
  it.each([12, 24])('separates %i collapsed community circles and long labels, then stops', count => {
    const before: GraphPoint[] = [
      { id: 1, x: 0, y: 0, width: 180, height: 80, anchorY: 28, fixed: false },
      ...Array.from({ length: count }, (_, i) => ({ id: i + 2, x: 200, y: 0, width: 180 + i % 3 * 30, height: 85, anchorY: 28, fixed: false })),
      { id: 100, x: -400, y: -400, width: 180, height: 80, anchorY: 28, fixed: false },
    ]
    const links = before.slice(1, -1).map(p => ({ id: p.id, source: 1, target: p.id }))
    const drag = new GraphDrag({ id: 1, kind: 'element' }, links, before)
    let current = drag.move(before, 500, 160), moving = true, frames = 0
    while (moving && frames++ < 1200) {
      const frame = drag.step(current, 1 / 60)
      current = frame.points; moving = frame.moving
    }
    expectFollowersSeparated(current.filter(p => p.id !== 100), new Set(links.map(e => e.target)))
    expect(frames).toBeLessThan(360)
    expect(moving).toBe(false)
    expect(current[0]).toMatchObject({ x: 500, y: 160 })
    expect(current.at(-1)).toBe(before.at(-1))
    expect(current.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
  })
  it('keeps the following group apart through several long drags and leaves unrelated nodes still', () => {
    let current: GraphPoint[] = [
      { id: 1, x: 0, y: 0, width: 150, height: 80, anchorY: 28, fixed: false },
      ...Array.from({ length: 16 }, (_, i) => ({ id: i + 2, x: Math.cos(i * Math.PI / 8) * 600, y: Math.sin(i * Math.PI / 8) * 600, width: 230, height: 96, anchorY: 28, fixed: false })),
      { id: 100, x: 750, y: 120, width: 240, height: 96, anchorY: 28, fixed: false },
    ]
    const obstacle = current.at(-1), links = current.slice(1, -1).map(p => ({ id: p.id, source: 1, target: p.id }))
    for (const [dx, dy] of [[900, 150], [-600, 500], [300, -650]]) {
      const initialCenterX = current.slice(1, -1).reduce((sum, p) => sum + p.x, 0) / links.length
      const drag = new GraphDrag({ id: 1, kind: 'element' }, links, current)
      for (let i = 0; i < 30; i++) current = drag.step(drag.move(current, dx / 30, dy / 30), 1 / 60).points
      let moving = true, frames = 0
      while (moving && frames++ < 1200) {
        const frame = drag.step(current, 1 / 60)
        current = frame.points; moving = frame.moving
      }
      expectFollowersSeparated(current.filter(p => p.id !== 100), new Set(links.map(e => e.target)))
      expect(moving).toBe(false)
      expect(current.at(-1)).toBe(obstacle)
      const centerX = current.slice(1, -1).reduce((sum, p) => sum + p.x, 0) / links.length
      if (dx === 900) expect(centerX - initialCenterX).toBeGreaterThan(300)
    }
  })
})
