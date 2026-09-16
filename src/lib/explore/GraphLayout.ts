import type { ElkNode } from 'elkjs/lib/elk-api'
import type { ExploreEdge, ExploreNode } from './types'

export type Coordinate = { x: number; y: number }
export type NodeSize = { width: number; height: number; anchorY: number }
export type GraphPoint = Coordinate & NodeSize & { id: number; fixed: boolean }
export type GraphDrawing = { points: GraphPoint[]; routes: Map<number, Coordinate[]> }

export function graphTitle(title: string) {
  return title.length > 30 ? title.slice(0, 29) + '…' : title
}

/** Node rectangles include the halo, title and optional property line. */
export function nodeSize(node: ExploreNode, measure: (text: string) => number = text => text.length * 10, propertyLabel = ''): NodeSize {
  return {
    width: Math.max(64, measure(graphTitle(node.title)) + 16, measure(propertyLabel) + 16),
    height: node.kind === 'community' ? (propertyLabel ? 85 : 69) : (propertyLabel ? 96 : 80),
    anchorY: 28,
  }
}

/** Finite initial layout; no simulation or collision constraints run while dragging. */
export class GraphLayout {
  constructor(private engine: { layout(graph: ElkNode): Promise<ElkNode> }) {}

  async arrange(nodes: ExploreNode[], edges: ExploreEdge[], sizes = new Map<number, NodeSize>(), previous: GraphPoint[] = [], direction: 'RIGHT' | 'DOWN' = 'RIGHT'): Promise<GraphDrawing> {
    const ordered = [...nodes].sort((a, b) => a.id - b.id)
    const ids = new Set(ordered.map(node => node.id))
    const links = edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)).sort((a, b) => a.id - b.id)
    const dimensions = new Map(ordered.map(node => [node.id, sizes.get(node.id) ?? nodeSize(node)]))
    const graph: ElkNode = {
      id: 'explore',
      layoutOptions: {
        'elk.algorithm': 'force',
        'elk.aspectRatio': direction === 'DOWN' ? '0.65' : '1.4',
        'elk.randomSeed': '1',
        'elk.force.iterations': '400',
        'elk.spacing.nodeNode': '24',
        // One organic cloud, including isolated nodes, rather than a grid of components.
        'elk.separateConnectedComponents': 'false',
        'elk.padding': '[top=24,left=24,bottom=24,right=24]',
      },
      children: ordered.map(node => ({ id: String(node.id), ...dimensions.get(node.id)! })),
      edges: links.map(edge => ({ id: String(edge.id), sources: [String(edge.source)], targets: [String(edge.target)] })),
    }
    if (!nodes.length) return { points: [], routes: new Map() }
    const result = await this.engine.layout(graph)
    const points = (result.children ?? []).map(child => {
      const id = Number(child.id), size = dimensions.get(id)!
      return { id, ...size, x: (child.x ?? 0) + size.width / 2, y: (child.y ?? 0) + size.height / 2, fixed: false }
    })
    this.pack(points)
    // Apply user positions only after automatic packing: manual overlaps are intentional.
    const old = new Map(previous.filter(point => point.fixed).map(point => [point.id, point]))
    for (const point of points) {
      const prior = old.get(point.id)
      if (prior) { point.x = prior.x; point.y = prior.y; point.fixed = true }
    }
    return { points, routes: new Map() }
  }

  /** Compact the force cloud, then find nearby free space without snapping to rows. */
  private pack(points: GraphPoint[]) {
    if (!points.length) return
    const center = {
      x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
      y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
    }
    const width = Math.max(...points.map(p => p.x + p.width / 2)) - Math.min(...points.map(p => p.x - p.width / 2))
    const height = Math.max(...points.map(p => p.y + p.height / 2)) - Math.min(...points.map(p => p.y - p.height / 2))
    const area = points.reduce((sum, p) => sum + p.width * p.height, 0)
    const compression = Math.min(0.8, Math.sqrt(area / (0.7 * width * height)))
    // Here x/y are rectangle centers; convert to circle anchors once all boxes fit.
    for (const point of points) {
      point.x = (point.x - center.x) * compression
      point.y = (point.y - center.y) * compression
    }
    const placed: GraphPoint[] = []
    const ordered = [...points].sort((a, b) => Math.hypot(a.x, a.y) - Math.hypot(b.x, b.y) || a.id - b.id)
    for (const point of ordered) {
      const target = { x: point.x, y: point.y }
      let attempt = 0
      while (placed.some(other => Math.abs(point.x - other.x) < (point.width + other.width) / 2 + 8 && Math.abs(point.y - other.y) < (point.height + other.height) / 2 + 8)) {
        // A golden-angle spiral samples all directions, including for identical centers.
        const angle = ++attempt * 2.399963229728653 + point.id * 0.73
        const radius = 6 * Math.sqrt(attempt)
        point.x = target.x + Math.cos(angle) * radius
        point.y = target.y + Math.sin(angle) * radius
      }
      placed.push(point)
    }
    for (const point of points) point.y += point.anchorY - point.height / 2
  }
}

/** Straight links keep the organic graph free of right-angle routing. */
export function edgeCoordinates(edge: ExploreEdge, byId: Map<number, GraphPoint>, routes: Map<number, Coordinate[]>): Coordinate[] {
  const a = byId.get(edge.source), b = byId.get(edge.target)
  if (!a || !b) return []
  return a.fixed || b.fixed ? [a, b] : [a, ...(routes.get(edge.id) ?? []), b]
}

export function edgePath(points: Coordinate[]) {
  return points.map((point, index) => `${index ? 'L' : 'M'}${point.x},${point.y}`).join(' ')
}
