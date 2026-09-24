import { describe, expect, it } from 'vitest'
import { SearchBackendProxy } from './SearchBackendProxy'

describe('SearchBackendProxy', () => {
  it('routes a public search URL internally while preserving the auth context', () => {
    const source = new Request('https://tambur.pub/api/search/?q=cinema', {
      headers: { Cookie: 'sessionid=test-session', Authorization: 'Bearer test-token' },
    })
    const result = new SearchBackendProxy('http://backend:8000/').resolve(source, 'https://tambur.pub')
    expect(result.url).toBe('http://backend:8000/api/search/?q=cinema')
    expect(result.headers.get('Cookie')).toBe('sessionid=test-session')
    expect(result.headers.get('Authorization')).toBe('Bearer test-token')
    expect(source.url).toBe('https://tambur.pub/api/search/?q=cinema')
  })

  it('does not redirect unrelated, external, or write requests', () => {
    const proxy = new SearchBackendProxy('http://backend:8000')
    for (const source of [new Request('https://other.test/api/search/'),
      new Request('https://tambur.pub/api/home/'),
      new Request('https://tambur.pub/api/search/', { method: 'POST' })]) {
      expect(proxy.resolve(source, 'https://tambur.pub')).toBe(source)
    }
    const source = new Request('https://tambur.pub/api/search/')
    expect(new SearchBackendProxy().resolve(source, 'https://tambur.pub')).toBe(source)
  })
})
