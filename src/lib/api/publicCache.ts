type CacheEntry<T> = {
  expiresAt: number
  promise: Promise<T>
}

const cache = new Map<string, CacheEntry<unknown>>()

export const invalidateCachedJson = (keyOrPrefix: string): void => {
  for (const key of Array.from(cache.keys())) {
    if (key === keyOrPrefix || key.startsWith(keyOrPrefix)) {
      cache.delete(key)
    }
  }
}

export const cachedJson = async <T>(
  key: string,
  url: string,
  options?: {
    ttlMs?: number
    fetcher?: typeof fetch
  }
): Promise<T> => {
  const ttlMs = options?.ttlMs ?? 60_000
  const now = Date.now()
  const cached = cache.get(key)
  if (cached && cached.expiresAt > now) {
    return cached.promise as Promise<T>
  }

  const fetcher = options?.fetcher ?? fetch
  const promise = fetcher(url).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return (await response.json()) as T
  })

  cache.set(key, {
    expiresAt: now + ttlMs,
    promise,
  })

  promise.catch(() => {
    const current = cache.get(key)
    if (current?.promise === promise) {
      cache.delete(key)
    }
  })

  return promise
}
