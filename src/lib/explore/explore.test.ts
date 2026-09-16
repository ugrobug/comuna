import { describe, expect, it } from 'vitest'
import { filterNodes, type ExploreNode, type ExploreProperty } from './types'
import ELK from 'elkjs/lib/elk.bundled.js'
import { GraphLayout, edgeCoordinates, nodeSize, type GraphPoint, type Coordinate } from './GraphLayout'

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
const bounds = (p: GraphPoint) => ({ left: p.x - p.width / 2, right: p.x + p.width / 2, top: p.y - p.anchorY, bottom: p.y - p.anchorY + p.height })
function expectNoOverlap(points: GraphPoint[]) {
  for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
    const a = bounds(points[i]), b = bounds(points[j])
    expect(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top).toBe(true)
  }
}
function crosses(a: Coordinate, b: Coordinate, c: Coordinate, d: Coordinate) {
  const side = (p: Coordinate, q: Coordinate, r: Coordinate) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
  return side(a, b, c) * side(a, b, d) < -0.001 && side(c, d, a) * side(c, d, b) < -0.001
}
const engine = new ELK()
const layout = new GraphLayout(engine)
describe('initial graph layout', () => {
  it('separates circles, long titles and property labels in a large graph', async () => {
    const nodes = Array.from({ length: 100 }, (_, i) => ({ ...node(i + 1, []), title: 'Очень длинное название увлечения ' + i }))
    const edges = nodes.slice(1).map(item => ({ id: item.id, source: Math.floor(item.id / 2), target: item.id }))
    edges.push({ id: 101, source: 3, target: 5 })
    const sizes = new Map(nodes.map(item => [item.id, nodeSize(item, text => text.length * 10, 'Можно одному · С друзьями')]))
    const drawing = await layout.arrange(nodes, edges, sizes)
    expect(drawing.points).toHaveLength(100)
    expect(drawing.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
    expectNoOverlap(drawing.points)
  })
  it.each(['RIGHT', 'DOWN'] as const)('keeps a branched cloud separated with straight links (%s)', async direction => {
    const nodes = Array.from({ length: 9 }, (_, i) => node(i + 1, []))
    const edges = [[1, 2], [1, 3], [2, 4], [3, 4], [5, 6], [5, 7], [7, 8]].map(([source, target], id) => ({ id, source, target }))
    const drawing = await layout.arrange(nodes, edges, new Map(), [], direction)
    expectNoOverlap(drawing.points)
    const byId = new Map(drawing.points.map(p => [p.id, p]))
    const lines = edges.map(edge => edgeCoordinates(edge, byId, drawing.routes))
    for (let i = 0; i < edges.length; i++) {
      for (let j = i + 1; j < edges.length; j++) {
        if ([edges[i].source, edges[i].target].some(id => id === edges[j].source || id === edges[j].target)) continue
        for (let a = 1; a < lines[i].length; a++) for (let b = 1; b < lines[j].length; b++) {
          expect(crosses(lines[i][a - 1], lines[i][a], lines[j][b - 1], lines[j][b])).toBe(false)
        }
      }
      expect(lines[i]).toHaveLength(2)

    }
  })
  it('packs disconnected interests into a compact irregular cloud', async () => {
    const drawing = await layout.arrange(Array.from({ length: 24 }, (_, i) => node(i + 1, [])), [])
    expectNoOverlap(drawing.points)
    const boxes = drawing.points.map(bounds)
    const width = Math.max(...boxes.map(b => b.right)) - Math.min(...boxes.map(b => b.left))
    const height = Math.max(...boxes.map(b => b.bottom)) - Math.min(...boxes.map(b => b.top))
    const area = drawing.points.reduce((sum, p) => sum + p.width * p.height, 0)
    expect(area / (width * height)).toBeGreaterThan(0.3)
    expect(new Set(drawing.points.map(p => Math.round(p.x))).size).toBeGreaterThan(18)
    expect(new Set(drawing.points.map(p => Math.round(p.y))).size).toBeGreaterThan(18)
  })
  it('separates coincident seed positions, including visible property labels', async () => {
    const nodes = Array.from({ length: 30 }, (_, i) => node(i + 1, []))
    const coincident = new GraphLayout({ layout: async graph => ({ ...graph, children: graph.children?.map(child => ({ ...child, x: 0, y: 0 })) }) })
    const sizes = new Map(nodes.map(n => [n.id, nodeSize(n, text => text.length * 10, 'Можно одному · С друзьями')]))
    expectNoOverlap((await coincident.arrange(nodes, [], sizes)).points)
  })
  it('supports cycles and dense nonplanar graphs without overlapping nodes', async () => {
    const nodes = Array.from({ length: 6 }, (_, i) => node(i + 1, []))
    const edges = [1, 2, 3].flatMap(source => [4, 5, 6].map(target => ({ id: source * 10 + target, source, target })))
    edges.push({ id: 100, source: 6, target: 1 })
    expectNoOverlap((await layout.arrange(nodes, edges)).points)
  })
  it('is deterministic across API node ordering and ignores filtered-out edges', async () => {
    const nodes = [node(1, []), node(2, []), node(3, [])]
    const edges = [{ id: 1, source: 1, target: 2 }, { id: 2, source: 2, target: 99 }]
    const a = await layout.arrange(nodes, edges), b = await layout.arrange([...nodes].reverse(), edges)
    expect(a.points).toEqual(b.points)
    expect(a.points).toEqual((await layout.arrange(nodes, edges.slice(0, 1))).points)
    expect(edgeCoordinates(edges[1], new Map(a.points.map(p => [p.id, p])), a.routes)).toEqual([])
    expect(await layout.arrange([], edges)).toEqual({ points: [], routes: new Map() })
  })
  it('allows manual overlap, keeps moved positions on filtering, and can reset them', async () => {
    const nodes = [node(1, []), node(2, [])], edges = [{ id: 1, source: 1, target: 2 }]
    const initial = await layout.arrange(nodes, edges)
    const [a, b] = initial.points
    a.x = b.x; a.y = b.y; a.fixed = true
    const path = edgeCoordinates(edges[0], new Map(initial.points.map(p => [p.id, p])), initial.routes)
    expect(path).toEqual([a, b])
    const next = await layout.arrange(nodes, edges, new Map(), initial.points)
    expect(next.points.find(p => p.id === 1)).toMatchObject({ x: a.x, y: a.y, fixed: true })
    expectNoOverlap((await layout.arrange(nodes, edges)).points)
  })
})
