import type { ExploreNode } from './types'

/** Private to this browser/profile. Positive IDs are picks, negative IDs are passes. */
export class HobbyHistory {
  static readonly limit = 5000
  constructor(private readonly key: string, private readonly storage?: Pick<Storage, 'getItem' | 'setItem'>) {}

  read(): number[] {
    try {
      const entries: unknown = JSON.parse(this.storage?.getItem(this.key) || '[]')
      return Array.isArray(entries) ? entries.slice(-HobbyHistory.limit).filter(id => Number.isSafeInteger(id) && id !== 0) : []
    } catch { return [] }
  }

  write(votes: number[]) {
    try { this.storage?.setItem(this.key, JSON.stringify(votes.slice(-HobbyHistory.limit))) }
    catch { /* Browsers with storage disabled can still use the current deck. */ }
  }
}

export class HobbyDeck {
  private readonly cards: ExploreNode[]
  private readonly byId: Map<number, ExploreNode>
  private readonly votes = new Map<number, number>()
  private readonly weights = new Map<number, number>()
  private readonly tie = new Map<number, number>()

  constructor(nodes: ExploreNode[], private readonly history: HobbyHistory, random = Math.random) {
    this.cards = nodes.filter(node => node.is_active && node.kind === 'element')
    this.byId = new Map(this.cards.map(node => [node.id, node]))
    for (const card of this.cards) this.tie.set(card.id, random())
    for (const signed of history.read()) this.record(Math.abs(signed), signed > 0)
  }

  get remaining() { return this.cards.length - this.votes.size }
  get picked() { return Array.from(this.votes.values()).filter(v => v > 0).map(id => this.byId.get(id)!) }

  private record(id: number, like: boolean) {
    const card = this.byId.get(id)
    if (!card || this.votes.has(id)) return false
    this.votes.set(id, like ? id : -id)
    for (const option of card.property_ids)
      this.weights.set(option, (this.weights.get(option) || 0) + (like ? 1 : -1))
    return true
  }

  choose(id: number, like: boolean) {
    if (!this.record(id, like)) return false
    this.history.write([...this.votes.values()])
    return true
  }

  next() {
    let best: ExploreNode | null = null, score = -Infinity
    for (const card of this.cards) {
      if (this.votes.has(card.id)) continue
      // Smooth each characteristic independently: one pass nudges, never excludes.
      // Random tie-break also gives an untagged card a chance.
      let affinity = 0
      for (const option of card.property_ids) {
        const w = this.weights.get(option) || 0
        affinity += w / (2 + Math.abs(w))
      }
      const rank = affinity / Math.sqrt(Math.max(1, card.property_ids.length)) + this.tie.get(card.id)! * .25
      if (rank > score) { score = rank; best = card }
    }
    return best
  }

  reset() {
    this.weights.clear(); this.votes.clear(); this.history.write([])
  }
}
