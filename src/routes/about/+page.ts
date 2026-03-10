import { buildRubricPostsUrl, buildStaticPageContentUrl } from '$lib/api/backend'
import { getDefaultStaticPageContent } from '$lib/staticPageContent'

const PAGE_SIZE = 10
const COMUNA_SLUG = 'comuna'
const STATIC_PAGE_SLUG = 'about'

export const load = async ({ fetch, url }) => {
  const requestUrl = new URL(buildRubricPostsUrl(COMUNA_SLUG), url.origin)
  requestUrl.searchParams.set('limit', String(PAGE_SIZE))

  const staticPageUrl = new URL(buildStaticPageContentUrl(STATIC_PAGE_SLUG), url.origin)
  const [postsResponse, pageResponse] = await Promise.all([
    fetch(requestUrl.toString()),
    fetch(staticPageUrl.toString(), { cache: 'no-store' }),
  ])

  let posts: any[] = []
  if (postsResponse.ok) {
    const data = await postsResponse.json().catch(() => ({}))
    posts = data.posts ?? []
  }

  let pageContent = getDefaultStaticPageContent('about')
  let pageExists = false
  if (pageResponse.ok) {
    const data = await pageResponse.json().catch(() => ({}))
    if (data?.page) {
      pageExists = !!data.page.exists
      if (pageExists) {
        pageContent = data.page.content ?? ''
      }
    }
  }

  return {
    posts,
    pageContent,
    pageExists,
  }
}
