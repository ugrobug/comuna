import type { GraphPoint } from './GraphLayout'

type Velocity = { vx: number; vy: number }

/** Separate followers using their full circle/label bounds; other nodes stay put. */
export class GraphCollision {
  static resolve(points: GraphPoint[], moving: Map<number, Velocity>): { overlap: number; adjusted: Set<number> } {
    let remaining = 0
    const adjusted = new Set<number>()
    for (let pass = 0; pass < 12; pass++) {
      remaining = 0
      for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
        const a = points[i], b = points[j], av = moving.get(a.id), bv = moving.get(b.id)
        if (!av && !bv) continue
        const dx = b.x - a.x, dy = b.y + b.height / 2 - b.anchorY - (a.y + a.height / 2 - a.anchorY)
        const overlapX = (a.width + b.width) / 2 + 10 - Math.abs(dx)
        const overlapY = (a.height + b.height) / 2 + 10 - Math.abs(dy)
        if (overlapX <= 0 || overlapY <= 0) continue
        remaining = Math.max(remaining, Math.min(overlapX, overlapY))
        // Prefer the shortest escape from the label rectangles, with a small diagonal
        // component so even collinear followers spread without snapping into rows.
        const slope = 0.18 + ((a.id * 13 + b.id * 7) % 11) / 50
        const sx = Math.sign(dx) || (a.id < b.id ? 1 : -1)
        const sy = Math.sign(dy) || ((a.id + b.id) % 2 ? 1 : -1)
        const ux = sx * (overlapX < overlapY ? 1 : slope) / Math.hypot(1, slope)
        const uy = sy * (overlapX < overlapY ? slope : 1) / Math.hypot(1, slope)
        const push = Math.min(overlapX / Math.max(Math.abs(ux), 1e-9), overlapY / Math.max(Math.abs(uy), 1e-9)) + 0.01
        const share = av && bv ? 0.5 : 1
        if (av) {
          adjusted.add(a.id)
          a.x -= ux * push * share; a.y -= uy * push * share
          const inward = Math.max(0, av.vx * ux + av.vy * uy)
          av.vx -= inward * ux; av.vy -= inward * uy
        }
        if (bv) {
          adjusted.add(b.id)
          b.x += ux * push * share; b.y += uy * push * share
          const inward = Math.min(0, bv.vx * ux + bv.vy * uy)
          bv.vx -= inward * ux; bv.vy -= inward * uy
        }
      }
      if (remaining < 0.05) break
    }
    return { overlap: remaining, adjusted }
  }
}
