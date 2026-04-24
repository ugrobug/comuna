import { buildStaticPageContentUrl } from '$lib/api/backend'
import { getDefaultStaticPageContent } from '$lib/staticPageContent'

const STATIC_PAGE_SLUG = 'about'

export const load = async ({ fetch, url }) => {
  const staticPageUrl = new URL(buildStaticPageContentUrl(STATIC_PAGE_SLUG), url.origin)
  const pageResponse = await fetch(staticPageUrl.toString(), { cache: 'no-store' })

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
    pageContent,
    pageExists,
  }
}
