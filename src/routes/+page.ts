import { buildFreshFeedUrl, buildHomeFeedUrl } from '$lib/api/backend'

const PAGE_SIZE = 10

export async function load({ fetch, url }) {
  const feedParam = url.searchParams.get('feed')
  const feedType =
    feedParam === 'fresh' ? 'fresh' : feedParam === 'mine' ? 'mine' : 'hot'

  let posts: any[] = []
  if (feedType !== 'mine') {
    try {
      const feedUrl =
        feedType === 'fresh' ? buildFreshFeedUrl() : buildHomeFeedUrl()
      const requestUrl = new URL(feedUrl, url.origin)
      requestUrl.searchParams.set('limit', String(PAGE_SIZE))
      const response = await fetch(requestUrl.toString())
      if (response.ok) {
        const data = await response.json()
        posts = data.posts ?? []
      }
    } catch (error) {
      console.error('Failed to load home feed:', error)
    }
  }

  return {
    posts,
    feedType,
  }
}
