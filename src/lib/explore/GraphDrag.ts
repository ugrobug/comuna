import { GraphCollision } from './GraphCollision'
import type { GraphPoint } from './GraphLayout'
import type { ExploreEdge, ExploreNode } from './types'

type Spring = { length: number; directionX: number; directionY: number; vx: number; vy: number }

/** The grabbed node follows the pointer; direct neighbors follow damped springs. */
export class GraphDrag {
  private readonly springs = new Map<number, Spring>()
  private readonly id: number
  private quietTime = 0
  private idleTime = 0
  private collided = false

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
    this.quietTime = 0; this.idleTime = 0
    return points.map(point => point.id === this.id
      ? { ...point, x: point.x + dx, y: point.y + dy, fixed: true }
      : point)
  }

  step(points: GraphPoint[], seconds: number): { points: GraphPoint[]; moving: boolean } {
    const anchor = points.find(point => point.id === this.id)
    if (!anchor || !this.springs.size || seconds <= 0) return { points, moving: false }
    // Small integration steps keep motion stable across refresh rates and suspended tabs.
    const duration = Math.min(seconds, 0.05), steps = Math.ceil(duration * 120), dt = duration / steps
    const next = points.map(point => this.springs.has(point.id) ? { ...point } : point)
    const group = next.filter(point => point.id === this.id || this.springs.has(point.id))
    let overlap = 0
    for (let i = 0; i < steps; i++) {
      this.idleTime += dt
      const cooling = this.collided ? Math.exp(-Math.max(0, this.idleTime - 0.35) * 2) : 1
      for (const point of next) {
        const spring = this.springs.get(point.id)
        if (!spring) continue
        const dx = point.x - anchor.x, dy = point.y - anchor.y, distance = Math.hypot(dx, dy)
        const ux = distance > 0.001 ? dx / distance : spring.directionX
        const uy = distance > 0.001 ? dy / distance : spring.directionY
        // Links pull when stretched, but go slack when the pointer approaches a
        // neighbor. Restoring a compressed long link would launch that neighbor
        // away from the group; only local collisions should push nodes apart.
        const force = -45 * cooling * Math.max(0, distance - spring.length)
        spring.vx = (spring.vx + force * ux * dt) * Math.exp(-7 * dt)
        spring.vy = (spring.vy + force * uy * dt) * Math.exp(-7 * dt)
        point.x += spring.vx * dt; point.y += spring.vy * dt
      }
      const collision = GraphCollision.resolve(group, this.springs)
      overlap = collision.overlap
      if (collision.adjusted.size) this.collided = true
    }
    let unsettled = overlap > 0.1, maxDisplacement = 0
    for (let i = 0; i < next.length; i++) {
      const point = next[i], spring = this.springs.get(point.id)
      if (!spring) continue
      const displacement = Math.hypot(point.x - points[i].x, point.y - points[i].y)
      maxDisplacement = Math.max(maxDisplacement, displacement)
      if (displacement > 0.01 || Math.hypot(spring.vx, spring.vy) > 0.2) unsettled = true
      if (displacement > 0.00001) point.fixed = true
    }
    // Cool contact forces after the pointer stops, avoiding perpetual pressure/jitter.
    // A new pointer move restores full spring strength immediately.
    this.quietTime = unsettled ? 0 : this.quietTime + duration
    const atRest = this.collided && this.idleTime > 3 && maxDisplacement < 0.1 && overlap < 0.1
    const moving = this.quietTime < 0.12 && !atRest
    if (!moving) for (const spring of this.springs.values()) { spring.vx = 0; spring.vy = 0 }
    return { points: next, moving }
  }
}
