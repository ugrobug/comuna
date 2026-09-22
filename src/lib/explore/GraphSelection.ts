import type { ExploreEdge, ExploreNode } from './types'
import type { GraphPoint } from './GraphLayout'

export type Viewport = { x: number; y: number; width: number; height: number }

/** Connections are traversable in either direction, without duplicates or self-links. */
export function connectedNodes(id: number, nodes: ExploreNode[], edges: ExploreEdge[]): ExploreNode[] {
  const ids = new Set(edges.flatMap(edge => edge.source === id ? [edge.target] : edge.target === id ? [edge.source] : []))
  ids.delete(id)
  return nodes.filter(node => ids.has(node.id)).sort((a, b) => a.title.localeCompare(b.title, 'ru'))
}

/** Fit the chosen nodes into the unobscured part of the canvas, leaving room for labels. */
export function focusNodes(points: GraphPoint[], viewport: Viewport) {
  if (!points.length || viewport.width <= 0 || viewport.height <= 0) return null
  const left = Math.min(...points.map(p => p.x - p.width / 2)) - 24
  const right = Math.max(...points.map(p => p.x + p.width / 2)) + 24
  const top = Math.min(...points.map(p => p.y - p.anchorY)) - 24
  const bottom = Math.max(...points.map(p => p.y - p.anchorY + p.height)) + 24
  const scale = Math.max(.03, Math.min(1.25, viewport.width / (right - left), viewport.height / (bottom - top)))
  return { scale, tx: viewport.x + viewport.width / 2 - (left + right) / 2 * scale,
    ty: viewport.y + viewport.height / 2 - (top + bottom) / 2 * scale }
}
