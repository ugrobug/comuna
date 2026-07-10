export const fetchWithTimeout = async (
  fetcher: typeof globalThis.fetch,
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number
): Promise<Response | null> => {
  const abortController = new AbortController()
  const timeoutId = setTimeout(() => abortController.abort(), timeoutMs)

  try {
    return await fetcher(input, {
      ...init,
      signal: abortController.signal,
    })
  } catch {
    return null
  } finally {
    clearTimeout(timeoutId)
  }
}
