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
    const before = points(), drag = new GraphDrag({ id: 1, kind: 'element' }, edges, before)
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
