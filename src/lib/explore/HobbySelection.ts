import type { ExploreData, ExploreNode } from './types'

export type SelectedHobby = { hobby: ExploreNode; communities: ExploreNode[] }

/** A read model shared by the selection page and its downloadable copy. */
export class HobbySelection {
  readonly items: SelectedHobby[]

  constructor(data: ExploreData, picks: ExploreNode[]) {
    const nodes = new Map(data.nodes.map(node => [node.id, node]))
    const related = new Map<number, Set<number>>()
    for (const pick of picks) related.set(pick.id, new Set())
    for (const {source, target} of data.edges) {
      related.get(source)?.add(target)
      related.get(target)?.add(source)
    }
    this.items = []
    for (const [id, neighbors] of related) {
      const hobby = nodes.get(id)
      if (!hobby?.is_active || hobby.kind !== 'element') continue
      const communities: ExploreNode[] = []
      for (const other of neighbors) {
        const node = nodes.get(other)
        if (node?.is_active && node.kind === 'community' && node.community_url) communities.push(node)
      }
      communities.sort((a,b) => (b.subscribers_count ?? 0) - (a.subscribers_count ?? 0)
        || a.title.localeCompare(b.title, 'ru') || a.id - b.id)
      this.items.push({hobby, communities})
    }
  }

  static description(node: ExploreNode) {
    const text = (node.community_description?.trim() || node.description || '').replace(/\s+/g, ' ').trim()
    if (text.length <= 280) return text
    return text.slice(0, 279).replace(/\s+\S*$/, '').trimEnd() + '…'
  }
}
