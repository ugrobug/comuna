import { describe, expect, it } from 'vitest'
import { connectedNodes, focusNodes } from './GraphSelection'
import type { ExploreNode } from './types'
import type { GraphPoint } from './GraphLayout'

const node = (id: number, title: string): ExploreNode => ({ id, title, kind: 'element', description: '', community_id: null, community_url: null, property_ids: [], show_properties: false, is_active: true, subscribed: false })

describe('exploring connections', () => {
  it('follows both incoming and outgoing edges, deduplicates and ignores self or missing nodes', () => {
    const nodes = [node(1, 'Спорт'), node(2, 'Бег'), node(3, 'Туризм'), node(4, 'Кино')]
    const edges = [[1, 2], [3, 1], [2, 1], [1, 1], [1, 99], [3, 4]].map(([source, target], id) => ({ id, source, target }))
    expect(connectedNodes(1, nodes, edges).map(n => n.id)).toEqual([2, 3])
    expect(connectedNodes(4, nodes, edges).map(n => n.id)).toEqual([3])
  })
  it.each([
    { x: 20, y: 100, width: 620, height: 500 },
    { x: 10, y: 125, width: 355, height: 190 },
  ])('keeps a selected neighborhood and its labels inside the area outside the card: %j', viewport => {
    const points: GraphPoint[] = [
      { id: 1, x: -600, y: 200, width: 240, height: 80, anchorY: 28, fixed: false },
      { id: 2, x: 200, y: -300, width: 160, height: 69, anchorY: 28, fixed: true },
    ]
    const view = focusNodes(points, viewport)!
    expect(view.scale).toBeGreaterThan(0)
    for (const p of points) {
      expect((p.x - p.width / 2) * view.scale + view.tx).toBeGreaterThanOrEqual(viewport.x)
      expect((p.x + p.width / 2) * view.scale + view.tx).toBeLessThanOrEqual(viewport.x + viewport.width)
      expect((p.y - p.anchorY) * view.scale + view.ty).toBeGreaterThanOrEqual(viewport.y)
      expect((p.y - p.anchorY + p.height) * view.scale + view.ty).toBeLessThanOrEqual(viewport.y + viewport.height)
    }
    expect(points[1].fixed).toBe(true)
  })
  it('does not change the camera when no points or no available viewport remain', () => {
    expect(focusNodes([], { x: 0, y: 0, width: 300, height: 200 })).toBeNull()
  })
})
