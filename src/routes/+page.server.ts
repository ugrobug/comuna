import { buildFavoritesFeedUrl, buildHomeFeedUrl, buildMyFeedUrl } from '$lib/api/backend'
import {
  languageFromAcceptLanguage,
  languageFromPathname,
  normalizeInterfaceLanguage,
  originalPostLanguage,
} from '$lib/postLanguages'
import type { PageServerLoad } from './$types'

const PAGE_SIZE = 10

type FeedType = 'hot' | 'mine' | 'favorites'

const normalizeFeedType = (value: string | null | undefined): FeedType | null => {
  if (value === 'mine' || value === 'favorites' || value === 'hot') return value
  return null
}

const authHeaders = (cookieHeader: string) =>
  cookieHeader ? { Cookie: cookieHeader } : undefined

const buildInitialFeedUrl = (
  feedType: FeedType,
  settings: Record<string, any> | null,
  readOnly: boolean,
  language: string
) => {
  const hideRead = Boolean(settings?.hide_read_posts) && !readOnly

  if (feedType === 'mine') {
    return buildMyFeedUrl(
      undefined,
      undefined,
      undefined,
      undefined,
      typeof settings?.my_feed_hide_negative === 'boolean'
        ? Boolean(settings.my_feed_hide_negative)
        : undefined,
      hideRead,
      readOnly,
      language
    )
  }

  if (feedType === 'favorites') {
    return buildFavoritesFeedUrl({
      hideRead,
      onlyRead: readOnly,
      language,
    })
  }

  return buildHomeFeedUrl({
    hideRead,
    onlyRead: readOnly,
    card: true,
    language,
  })
}

export const load: PageServerLoad = async ({ fetch, parent, request, url }) => {
  const explicitFeedType = normalizeFeedType(url.searchParams.get('feed'))
  const readParam = url.searchParams.get('read')
  const readOnly = readParam === '1' || readParam === 'true' || readParam === 'yes'
  const cookieHeader = request.headers.get('cookie') || ''
  const parentData = await parent()
  const settings = parentData.authBootstrap?.settings ?? null
  const authenticated = Boolean(parentData.authBootstrap?.user)
  const savedFeedType = normalizeFeedType(settings?.home_feed)
  const feedType = explicitFeedType ?? savedFeedType ?? 'hot'
  const language =
    normalizeInterfaceLanguage(settings?.interface_language) ||
    languageFromPathname(url.pathname) ||
    languageFromAcceptLanguage(request.headers.get('accept-language')) ||
    originalPostLanguage

  let posts: any[] = []
  let serverLoadedFeed = false
  const shouldLoadAuthenticatedFeed = authenticated || feedType === 'hot'

  if (shouldLoadAuthenticatedFeed) {
    try {
      const requestUrl = new URL(
        buildInitialFeedUrl(feedType, settings, readOnly, language),
        url.origin
      )
      requestUrl.searchParams.set('limit', String(PAGE_SIZE))
      const response = await fetch(requestUrl.toString(), {
        headers:
          authenticated && (feedType !== 'hot' || Boolean(settings?.hide_read_posts) || readOnly)
            ? authHeaders(cookieHeader)
            : undefined,
      })
      if (response.ok) {
        const data = await response.json()
        posts = data.posts ?? []
        serverLoadedFeed = true
      }
    } catch (error) {
      console.error('Failed to load initial home feed:', error)
    }
  }

  return {
    posts,
    feedType,
    authenticated,
    serverLoadedFeed,
  }
}
