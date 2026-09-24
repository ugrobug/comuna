export type SuggestionState<T> = {
  open: boolean
  loading: boolean
  payload?: T
  failed?: boolean
}

type SuggestionResponse<T> = { payload: T; cacheable: boolean }

/** Owns the lifetime of input-driven requests; never runs on URL synchronization. */
export class SuggestionController<T> {
  private timer?: ReturnType<typeof setTimeout>
  private abort?: AbortController
  private revision = 0
  private cache = new Map<string, { payload: T; expires: number }>()

  constructor(
    private load: (query: string, signal: AbortSignal) => Promise<SuggestionResponse<T>>,
    private changed: (state: SuggestionState<T>) => void,
    private delay = 220,
  ) {}

  search(raw: string) {
    this.cancel()
    const query = raw.trim()
    if (query.length < 2) {
      this.changed({ open: false, loading: false })
      return
    }
    const cached = this.cache.get(query)
    if (cached && cached.expires > Date.now()) {
      this.changed({ open: true, loading: false, payload: cached.payload })
      return
    }
    this.changed({ open: true, loading: true })
    const revision = this.revision
    this.timer = setTimeout(() => void this.run(query, revision), this.delay)
  }

  close() {
    this.cancel()
    this.changed({ open: false, loading: false })
  }

  destroy() {
    this.close()
    this.cache.clear()
  }

  private cancel() {
    this.revision++
    if (this.timer) clearTimeout(this.timer)
    this.timer = undefined
    this.abort?.abort()
    this.abort = undefined
  }

  private async run(query: string, revision: number) {
    this.timer = undefined
    this.abort = new AbortController()
    try {
      const result = await this.load(query, this.abort.signal)
      if (revision !== this.revision) return
      // Authenticated/dynamic invitation responses must never enter this cache.
      if (result.cacheable) {
        this.cache.delete(query)
        this.cache.set(query, { payload: result.payload, expires: Date.now() + 10_000 })
        if (this.cache.size > 20) this.cache.delete(this.cache.keys().next().value!)
      }
      this.changed({ open: true, loading: false, payload: result.payload })
    } catch {
      if (revision === this.revision) this.changed({ open: true, loading: false, failed: true })
    } finally {
      if (revision === this.revision) this.abort = undefined
    }
  }
}
