import type { ExploreEdge, ExploreNode } from './types'

export type GraphPoint = { id: number; x: number; y: number; vx: number; vy: number; fixed: boolean }

/** Deterministic, bounded force layout. Rendering and user interactions live separately. */
export class GraphLayout {
  points: GraphPoint[]
  private links: [GraphPoint, GraphPoint][]
  private iteration = 0

  constructor(nodes: ExploreNode[], edges: ExploreEdge[], previous: GraphPoint[] = []) {
    const old = new Map(previous.map(point => [point.id, point]))
    this.points = nodes.map((node, index) => {
      const prior = old.get(node.id)
      const angle = index * 2.399963
      const radius = 45 * Math.sqrt(index + 1)
      return { id: node.id, x: prior?.x ?? 500 + Math.cos(angle) * radius, y: prior?.y ?? 325 + Math.sin(angle) * radius, vx: 0, vy: 0, fixed: false }
    })
    const byId = new Map(this.points.map(point => [point.id, point]))
    this.links = edges.flatMap(edge => {
      const a = byId.get(edge.source), b = byId.get(edge.target)
      return a && b ? [[a, b] as [GraphPoint, GraphPoint]] : []
    })
  }

  step() {
    const cooling = Math.max(0.04, 1 - this.iteration / 180)
    for (let i = 0; i < this.points.length; i++) {
      const a = this.points[i]
      for (let j = i + 1; j < this.points.length; j++) {
        const b = this.points[j]
        const dx = a.x - b.x || 0.01, dy = a.y - b.y || 0.01
        const distance = Math.max(20, Math.hypot(dx, dy))
        const force = Math.min(12, 5200 / (distance * distance)) * cooling
        a.vx += dx / distance * force; a.vy += dy / distance * force
        b.vx -= dx / distance * force; b.vy -= dy / distance * force
      }
    }
    for (const [a, b] of this.links) {
      const dx = b.x - a.x, dy = b.y - a.y
      const distance = Math.max(1, Math.hypot(dx, dy))
      const force = (distance - 155) * 0.018 * cooling
      a.vx += dx / distance * force; a.vy += dy / distance * force
      b.vx -= dx / distance * force; b.vy -= dy / distance * force
    }
    for (const point of this.points) {
      point.vx = (point.vx + (500 - point.x) * 0.001 * cooling) * 0.72
      point.vy = (point.vy + (325 - point.y) * 0.001 * cooling) * 0.72
      if (!point.fixed) { point.x += point.vx; point.y += point.vy }
    }
    return ++this.iteration < 190
  }
}
