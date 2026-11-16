import { describe, expect, it } from 'vitest'
import { HobbySelection } from './HobbySelection'
import { emptyGraph, type ExploreNode } from './types'

function node(id: number, kind: ExploreNode['kind'], extra: Partial<ExploreNode> = {}): ExploreNode {
  return {id, kind, title: String(id), description: '', property_ids: [], show_properties: false,
    is_active: true, subscribed: false, community_id: null, community_url: kind === 'community' ? '/comuns/' + id : null, ...extra}
}

describe('hobby selection shared with PDF', () => {
  it('preserves pick order and all distinct visible communities in both edge directions', () => {
    const graph = emptyGraph()
    const hobby = node(1, 'element'), other = node(2, 'element'), empty = node(3, 'element')
    const clubs = [11, 12, 13, 14, 15].map(id => node(id, 'community', {subscribers_count: id}))
    graph.nodes = [hobby, other, empty, ...clubs, node(16, 'community', {is_active: false})]
    const links = [[1, 11], [12, 1], [1, 12], [1, 13], [1, 14], [1, 15], [1, 16], [2, 11], [1, 2]]
    graph.edges = links.map(([source, target], id) => ({source, target, id}))
    const selection = new HobbySelection(graph, [empty, hobby, other, node(99, 'element')])
    expect(selection.items.map(item => [item.hobby.id, item.communities.map(c => c.id)]))
      .toEqual([[3, []], [1, [15, 14, 13, 12, 11]], [2, [11]]])
  })

  it('uses the community description and keeps long summaries brief', () => {
    const club = node(8, 'community', {description: 'Из графа', community_description: ' О клубе. '})
    expect(HobbySelection.description(club)).toBe('О клубе.')
    expect(HobbySelection.description({...club, community_description: ''})).toBe('Из графа')
    const summary = HobbySelection.description({...club, community_description: 'Длинное описание. '.repeat(30)})
    expect(summary.endsWith('…')).toBe(true)
    expect(summary.length).toBeLessThanOrEqual(280)
  })
})
