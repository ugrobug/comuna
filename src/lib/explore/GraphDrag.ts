import type { GraphPoint } from './GraphLayout'
import type { ExploreEdge, ExploreNode } from './types'

/** A drag moves one interest and its direct neighbors as a single group. */
export class GraphDrag {
  private readonly ids: Set<number>

  constructor(node: Pick<ExploreNode, 'id' | 'kind'>, edges: ExploreEdge[]) {
    this.ids = new Set([node.id])
    if (node.kind === 'element') {
      for (const edge of edges) {
        if (edge.source === node.id) this.ids.add(edge.target)
        if (edge.target === node.id) this.ids.add(edge.source)
      }
    }
  }

  move(points: GraphPoint[], dx: number, dy: number): GraphPoint[] {
    return points.map(point => this.ids.has(point.id)
      ? { ...point, x: point.x + dx, y: point.y + dy, fixed: true }
      : point)
  }
}
