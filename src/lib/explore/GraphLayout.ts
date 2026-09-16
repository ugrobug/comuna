import type { ELK, ElkNode } from 'elkjs/lib/elk-api'
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
    width: Math.max(88, measure(graphTitle(node.title)) + 24, measure(propertyLabel) + 24),
    height: node.kind === 'community' ? (propertyLabel ? 110 : 94) : (propertyLabel ? 121 : 105),
    anchorY: 38,
  }
}

/** Finite initial layout; no simulation or collision constraints run while dragging. */
export class GraphLayout {
  constructor(private engine: Pick<ELK, 'layout'>) {}

  async arrange(nodes: ExploreNode[], edges: ExploreEdge[], sizes = new Map<number, NodeSize>(), previous: GraphPoint[] = [], direction: 'RIGHT' | 'DOWN' = 'RIGHT'): Promise<GraphDrawing> {
    const ordered = [...nodes].sort((a, b) => a.id - b.id)
    const ids = new Set(ordered.map(node => node.id))
    const links = edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)).sort((a, b) => a.id - b.id)
    const dimensions = new Map(ordered.map(node => [node.id, sizes.get(node.id) ?? nodeSize(node)]))
    const graph: ElkNode = {
      id: 'explore',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': direction,
        'elk.aspectRatio': direction === 'DOWN' ? '0.6' : '1.6',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.randomSeed': '1',
        'elk.spacing.nodeNode': '44',
        'elk.spacing.componentComponent': '70',
        'elk.spacing.edgeNode': '24',
        'elk.spacing.edgeEdge': '14',
        'elk.layered.spacing.nodeNodeBetweenLayers': '80',
        'elk.layered.spacing.edgeNodeBetweenLayers': '24',
        'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
        'elk.layered.crossingMinimization.greedySwitch.type': 'TWO_SIDED',
        'elk.layered.thoroughness': '20',
        'elk.separateConnectedComponents': 'true',
        'elk.padding': '[top=24,left=24,bottom=24,right=24]',
      },
      children: ordered.map(node => {
        const size = dimensions.get(node.id)!
        return {
          id: String(node.id), width: size.width, height: size.height,
          layoutOptions: { 'elk.portConstraints': 'FIXED_POS' },
          ports: [
            { id: `${node.id}-in`, x: 0, y: size.anchorY, width: 0, height: 0, layoutOptions: { 'elk.port.side': 'WEST' } },
            { id: `${node.id}-out`, x: size.width, y: size.anchorY, width: 0, height: 0, layoutOptions: { 'elk.port.side': 'EAST' } },
          ],
        }
      }),
      edges: links.map(edge => ({ id: String(edge.id), sources: [`${edge.source}-out`], targets: [`${edge.target}-in`] })),
    }
    if (!nodes.length) return { points: [], routes: new Map() }
    const result = await this.engine.layout(graph)
    const old = new Map(previous.filter(point => point.fixed).map(point => [point.id, point]))
    const points = (result.children ?? []).map(child => {
      const id = Number(child.id), size = dimensions.get(id)!, prior = old.get(id)
      return { id, ...size, x: prior?.x ?? (child.x ?? 0) + size.width / 2, y: prior?.y ?? (child.y ?? 0) + size.anchorY, fixed: Boolean(prior) }
    })
    const routes = new Map<number, Coordinate[]>()
    for (const edge of result.edges ?? []) {
      const section = edge.sections?.[0]
      if (section) routes.set(Number(edge.id), [section.startPoint, ...(section.bendPoints ?? []), section.endPoint])
    }
    return { points, routes }
  }
}

/** Only an edge incident to a manually moved node switches to a free straight line. */
export function edgeCoordinates(edge: ExploreEdge, byId: Map<number, GraphPoint>, routes: Map<number, Coordinate[]>): Coordinate[] {
  const a = byId.get(edge.source), b = byId.get(edge.target)
  if (!a || !b) return []
  return a.fixed || b.fixed ? [a, b] : [a, ...(routes.get(edge.id) ?? []), b]
}

export function edgePath(points: Coordinate[]) {
  return points.map((point, index) => `${index ? 'L' : 'M'}${point.x},${point.y}`).join(' ')
}
