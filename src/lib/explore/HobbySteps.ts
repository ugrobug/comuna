import type { ExploreNode } from './types'

/** A revised instruction starts unchecked, even on a previously completed card. */
export class HobbySteps {
  private readonly marks = new Map<number, string>()

  constructor(private readonly scope: string, private readonly storage?: Storage) {}

  isDone(node: ExploreNode): boolean {
    if (!node.try_step) return false
    if (!this.marks.has(node.id)) {
      try { this.marks.set(node.id, this.storage?.getItem(this.key(node.id)) ?? '') }
      catch { return false }
    }
    return this.marks.get(node.id) === node.try_step
  }

  set(node: ExploreNode, checked: boolean) {
    const step = checked ? node.try_step ?? '' : ''
    this.marks.set(node.id, step)
    try {
      if (step) this.storage?.setItem(this.key(node.id), step)
      else this.storage?.removeItem(this.key(node.id))
    } catch { /* The mark is still available in this session. */ }
  }

  private key(id: number) { return this.scope + ':step:' + id }
}
