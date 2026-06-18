import { browser } from '$app/environment'
import { invalidateAll } from '$app/navigation'
import { page } from '$app/stores'
import { loadSidebarComuns } from '$lib/communitySidebar'
import { userSettings } from '$lib/settings'
import { get } from 'svelte/store'

const normalizedPathname = (url: URL) => {
  const path = url.pathname.replace(/\/+$/, '')
  return path || '/'
}

export const shouldInvalidatePageAfterSiteAuth = (url: URL) => {
  const pathname = normalizedPathname(url)
  if (pathname === '/comuns') return true
  if (pathname !== '/') return false
  const feed = url.searchParams.get('feed') ?? get(userSettings).homeFeed ?? 'hot'
  return feed === 'mine'
}

export const refreshAfterSiteAuth = async () => {
  if (!browser) return
  const currentPage = get(page)
  if (shouldInvalidatePageAfterSiteAuth(currentPage.url)) {
    await invalidateAll()
    return
  }
  await loadSidebarComuns()
}
