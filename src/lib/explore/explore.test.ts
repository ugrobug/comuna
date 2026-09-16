import { describe, expect, it } from 'vitest'
import { filterNodes, type ExploreNode, type ExploreProperty } from './types'
import { GraphLayout } from './GraphLayout'

const node = (id: number, properties: number[]): ExploreNode => ({ id, title: `Увлечение ${id}`, kind: 'element', description: '', property_ids: properties, show_properties: false, is_active: true, community_id: null, community_url: null, subscribed: false })
const properties: ExploreProperty[] = [
  { id: 1, key: 'company', name: 'Компания', options: [{ id: 1, label: 'Одному' }, { id: 2, label: 'С друзьями' }] },
  { id: 2, key: 'danger', name: 'Опасность', options: [{ id: 3, label: 'Безопасно' }, { id: 4, label: 'Экстремально' }] },
]
describe('Explore filters', () => {
  const nodes = [node(1, [1, 3]), node(2, [2, 3]), node(3, [2, 4]), node(4, [])]
  it('uses OR inside a property and AND between properties', () => {
    expect(filterNodes(nodes, properties, [1, 2, 3], '').map(item => item.id)).toEqual([1, 2])
  })
  it('filters hidden properties and excludes unset properties when required', () => {
    expect(filterNodes(nodes, properties, [4], '').map(item => item.id)).toEqual([3])
    expect(filterNodes(nodes, properties, [], '')).toHaveLength(4)
  })
  it('combines search and filters', () => {
    expect(filterNodes(nodes, properties, [3], ' УВЛЕЧЕНИЕ 2 ').map(item => item.id)).toEqual([2])
  })
})
describe('graph layout', () => {
  it('keeps a graph with multiple parents finite and settles within bounded steps', () => {
    const nodes = Array.from({ length: 100 }, (_, i) => node(i + 1, []))
    const edges = nodes.slice(1).map(item => ({ id: item.id, source: Math.floor(item.id / 2), target: item.id }))
    edges.push({ id: 101, source: 3, target: 5 })
    const layout = new GraphLayout(nodes, edges)
    for (let i = 0; i < 190; i++) layout.step()
    expect(layout.step()).toBe(false)
    expect(layout.points.every(point => Number.isFinite(point.x) && Number.isFinite(point.y))).toBe(true)
    expect(new Set(layout.points.map(point => `${point.x},${point.y}`)).size).toBe(100)
  })
  it('preserves user positions when rebuilding and tolerates filtered-out edges', () => {
    const layout = new GraphLayout([node(1, [])], [{ id: 1, source: 1, target: 2 }], [{ id: 1, x: 100, y: 200, vx: 0, vy: 0, fixed: true }])
    expect(layout.points[0].x).toBe(100)
    expect(() => layout.step()).not.toThrow()
  })
})
