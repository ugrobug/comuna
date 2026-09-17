import type { Coordinate } from './GraphLayout'

export type GraphView = { scale: number; tx: number; ty: number }

/** Keep the graph point between two fingers under their moving midpoint. */
export class GraphPinch {
  private readonly distance: number
  private readonly anchor: Coordinate

  constructor(a: Coordinate, b: Coordinate, private readonly view: GraphView) {
    this.distance = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y))
    this.anchor = { x: ((a.x + b.x) / 2 - view.tx) / view.scale, y: ((a.y + b.y) / 2 - view.ty) / view.scale }
  }

  move(a: Coordinate, b: Coordinate): GraphView {
    const scale = Math.max(.03, Math.min(3, this.view.scale * Math.hypot(b.x - a.x, b.y - a.y) / this.distance))
    return { scale, tx: (a.x + b.x) / 2 - this.anchor.x * scale, ty: (a.y + b.y) / 2 - this.anchor.y * scale }
  }
}
