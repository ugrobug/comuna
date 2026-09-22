export type ExploreNode = {
  id: number
  kind: 'element' | 'community'
  title: string
  description: string
  image_url?: string | null
  community_description?: string
  subscribers_count?: number | null
  property_ids: number[]
  show_properties: boolean
  is_active: boolean
  community_id: number | null
  community_url: string | null
  subscribed: boolean
}
export type ExploreEdge = { id: number; source: number; target: number }
export type ExploreProperty = { id: number; key: string; name: string; options: { id: number; label: string }[] }
export type ExploreData = {
  nodes: ExploreNode[]
  edges: ExploreEdge[]
  properties: ExploreProperty[]
  communities?: { id: number; name: string; slug: string }[]
}

export const emptyGraph = (): ExploreData => ({ nodes: [], edges: [], properties: [] })

export function filterNodes(nodes: ExploreNode[], properties: ExploreProperty[], selected: number[], query: string) {
  const groups = properties.map(property => property.options.filter(option => selected.includes(option.id)).map(option => option.id)).filter(group => group.length)
  const search = query.trim().toLocaleLowerCase('ru')
  return nodes.filter(node => (!search || `${node.title} ${node.description}`.toLocaleLowerCase('ru').includes(search))
    && groups.every(group => group.some(id => node.property_ids.includes(id))))
}
