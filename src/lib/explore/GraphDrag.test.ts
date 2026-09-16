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

describe('interest group dragging', () => {
  it('moves incoming and outgoing neighbors together, leaving indirect and unrelated nodes still', () => {
    const before = points()
    const after = new GraphDrag({ id: 1, kind: 'element' }, edges).move(before, 40, -25)
    for (const point of after) {
      const old = before.find(item => item.id === point.id)!
      if ([1, 2, 3].includes(point.id)) expect(point).toEqual({ ...old, x: old.x + 40, y: old.y - 25, fixed: true })
      else expect(point).toBe(old)
    }
    expect(before.every(point => !point.fixed)).toBe(true)
  })
  it('does not multiply movement for duplicate links, cycles or self links', () => {
    const drag = new GraphDrag({ id: 1, kind: 'element' }, [...edges, { id: 5, source: 2, target: 1 }, { id: 6, source: 1, target: 1 }])
    const after = drag.move(drag.move(points(), 10, 20), -3, 5)
    expect(after[0]).toMatchObject({ x: 7, y: 25 })
    expect(after[1]).toMatchObject({ x: 87, y: 55 })
    expect(after[3]).toMatchObject({ x: 240, y: 90, fixed: false })
  })
  it('lets a community move individually', () => {
    const before = points()
    const after = new GraphDrag({ id: 2, kind: 'community' }, edges).move(before, -20, 30)
    expect(after[1]).toMatchObject({ x: 60, y: 60, fixed: true })
    expect(after.filter(point => point.fixed).map(point => point.id)).toEqual([2])
  })
  it('handles filtered-out neighbors and isolated interests without adding nodes', () => {
    const after = new GraphDrag({ id: 1, kind: 'element' }, edges).move(points().slice(0, 1), 5, 8)
    expect(after).toHaveLength(1)
    expect(after[0]).toMatchObject({ x: 5, y: 8, fixed: true })
    expect(new GraphDrag({ id: 5, kind: 'element' }, edges).move(points(), 5, 8).filter(p => p.fixed).map(p => p.id)).toEqual([5])
  })
})
