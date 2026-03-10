import { buildStaticPageContentUrl } from '$lib/api/backend'
import { getDefaultStaticPageContent } from '$lib/staticPageContent'

const STATIC_PAGE_SLUG = 'advertisement'

export const load = async ({ fetch, url }) => {
  const requestUrl = new URL(buildStaticPageContentUrl(STATIC_PAGE_SLUG), url.origin)
  const response = await fetch(requestUrl.toString(), { cache: 'no-store' })

  let pageContent = getDefaultStaticPageContent('advertisement')
  let pageExists = false

  if (response.ok) {
    const data = await response.json().catch(() => ({}))
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
