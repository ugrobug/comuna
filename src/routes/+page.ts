import {
  buildFreshFeedUrl,
  buildHomeFeedUrl,
  buildThematicFeedPostsUrl,
} from '$lib/api/backend'

const PAGE_SIZE = 10

export async function load({ fetch, url }) {
  const feedParam = url.searchParams.get('feed')
  const thematicSlug = (url.searchParams.get('theme') ?? '').trim()
  const feedType =
    feedParam === 'fresh'
      ? 'fresh'
      : feedParam === 'mine'
        ? 'mine'
        : feedParam === 'favorites'
          ? 'favorites'
          : feedParam === 'thematic'
            ? 'thematic'
          : 'hot'

  let posts: any[] = []
  let thematicFeed: any = null
  if (feedType === 'hot' || feedType === 'fresh' || (feedType === 'thematic' && thematicSlug)) {
    try {
      const feedUrl =
        feedType === 'fresh'
          ? buildFreshFeedUrl()
          : feedType === 'thematic'
            ? buildThematicFeedPostsUrl(thematicSlug)
            : buildHomeFeedUrl()
      const requestUrl = new URL(feedUrl, url.origin)
      requestUrl.searchParams.set('limit', String(PAGE_SIZE))
      const response = await fetch(requestUrl.toString())
      if (response.ok) {
        const data = await response.json()
        posts = data.posts ?? []
        thematicFeed = data.thematic_feed ?? null
      }
    } catch (error) {
      console.error('Failed to load home feed:', error)
    }
  }

  return {
    posts,
    feedType,
    thematicSlug,
    thematicFeed,
  }
}
