import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchWithTimeout } from '../src/lib/fetchWithTimeout'

afterEach(() => {
  vi.useRealTimers()
})

describe('fetchWithTimeout', () => {
  it('aborts a stalled request and returns null', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('Request aborted', 'AbortError'))
        })
      })
    ) as unknown as typeof globalThis.fetch

    const responsePromise = fetchWithTimeout(
      fetcher,
      new URL('https://tambur.pub/api/content-pages/apps/'),
      { cache: 'no-store' },
      2_500
    )

    await vi.advanceTimersByTimeAsync(2_500)

    await expect(responsePromise).resolves.toBeNull()
  })
})
