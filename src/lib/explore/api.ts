import { get } from 'svelte/store'
import { siteToken } from '$lib/siteAuth'
import { getBackendBaseUrl } from '$lib/api/backend'
import type { ExploreData } from './types'

export class ExploreApi {
  async request<T>(path = '', method = 'GET', body?: unknown): Promise<T> {
    const token = get(siteToken)
    const response = await fetch(`${getBackendBaseUrl()}/api/explore/${path}`, {
      method, credentials: 'include',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.error || 'Не удалось выполнить действие. Попробуйте ещё раз.')
    return payload as T
  }
  graph(manage = false) { return this.request<ExploreData>(manage ? 'manage/' : '') }
  saveNode(data: unknown, id?: number) { return this.request<{ id: number }>(id ? `nodes/${id}/` : 'nodes/', id ? 'PATCH' : 'POST', data) }
  removeNode(id: number) { return this.request(`nodes/${id}/`, 'DELETE') }
  addEdge(source: number, target: number) { return this.request('edges/', 'POST', { source, target }) }
  removeEdge(id: number) { return this.request(`edges/${id}/`, 'DELETE') }
  subscribe(id: number, enabled: boolean) { return this.request<{ subscribed: boolean }>(`nodes/${id}/subscription/`, enabled ? 'POST' : 'DELETE') }
}
