/** Keep the public search fetch URL identical during SSR and hydration. */
export class SearchBackendProxy {
  constructor(private internalBase?: string) {}

  resolve(request: Request, origin: string): Request {
    const url = new URL(request.url)
    if (!this.internalBase || url.origin !== origin || request.method !== 'GET' ||
        !['/api/search/', '/api/search/suggest/'].includes(url.pathname)) return request
    return new Request(`${this.internalBase.replace(/\/$/, '')}${url.pathname}${url.search}`, request)
  }
}
