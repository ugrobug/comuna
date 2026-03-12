import { buildStaticPageContentUrl } from '$lib/api/backend'
import { getDefaultStaticPageContent, type EditableStaticPageSlug } from '$lib/staticPageContent'

export const loadEditableStaticPage = async (
  { fetch, url }: { fetch: typeof globalThis.fetch; url: URL },
  slug: EditableStaticPageSlug
) => {
  const requestUrl = new URL(buildStaticPageContentUrl(slug), url.origin)
  const response = await fetch(requestUrl.toString(), { cache: 'no-store' })

  let pageContent = getDefaultStaticPageContent(slug)
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
