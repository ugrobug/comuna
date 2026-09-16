import type { GraphPoint } from './GraphLayout'
import type { ExploreEdge, ExploreNode } from './types'

type Spring = { length: number; directionX: number; directionY: number; vx: number; vy: number }

/** The grabbed node follows the pointer; direct neighbors follow damped springs. */
export class GraphDrag {
  private readonly springs = new Map<number, Spring>()
  private readonly id: number

  constructor(node: Pick<ExploreNode, 'id' | 'kind'>, edges: ExploreEdge[], points: GraphPoint[]) {
    this.id = node.id
    const anchor = points.find(point => point.id === node.id)
    if (node.kind !== 'element' || !anchor) return
    const neighbors = new Set(edges.flatMap(edge => edge.source === node.id ? [edge.target] : edge.target === node.id ? [edge.source] : []))
    for (const point of points) {
      if (point.id === node.id || !neighbors.has(point.id)) continue
      const dx = point.x - anchor.x, dy = point.y - anchor.y, length = Math.hypot(dx, dy)
      this.springs.set(point.id, { length, directionX: length ? dx / length : 1, directionY: length ? dy / length : 0, vx: 0, vy: 0 })
    }
  }

  move(points: GraphPoint[], dx: number, dy: number): GraphPoint[] {
    return points.map(point => point.id === this.id
      ? { ...point, x: point.x + dx, y: point.y + dy, fixed: true }
      : point)
  }

  step(points: GraphPoint[], seconds: number): { points: GraphPoint[]; moving: boolean } {
    const anchor = points.find(point => point.id === this.id)
    if (!anchor || seconds <= 0) return { points, moving: false }
    // Small integration steps keep motion stable across refresh rates and suspended tabs.
    const duration = Math.min(seconds, 0.05), steps = Math.ceil(duration * 120), dt = duration / steps
    let moving = false
    const next = points.map(point => {
      const spring = this.springs.get(point.id)
      if (!spring) return point
      let x = point.x, y = point.y
      for (let i = 0; i < steps; i++) {
        const dx = x - anchor.x, dy = y - anchor.y, distance = Math.hypot(dx, dy)
        const ux = distance > 0.001 ? dx / distance : spring.directionX
        const uy = distance > 0.001 ? dy / distance : spring.directionY
        const force = -45 * (distance - spring.length)
        spring.vx = (spring.vx + force * ux * dt) * Math.exp(-7 * dt)
        spring.vy = (spring.vy + force * uy * dt) * Math.exp(-7 * dt)
        x += spring.vx * dt; y += spring.vy * dt
      }
      const unsettled = Math.abs(Math.hypot(x - anchor.x, y - anchor.y) - spring.length) > 0.1 || Math.hypot(spring.vx, spring.vy) > 0.2
      if (unsettled) moving = true
      else { spring.vx = 0; spring.vy = 0 }
      return Math.hypot(x - point.x, y - point.y) > 0.00001 ? { ...point, x, y, fixed: true } : point
    })
    return { points: next, moving }
  }
}
