import { buildStaticPageContentUrl, type BackendStaticPageLanguageVersion } from '$lib/api/backend'
import { fetchWithTimeout } from '$lib/fetchWithTimeout'
import { languageFromPathname, originalPostLanguage } from '$lib/postLanguages'
import { getLocalizedDefaultStaticPage, type EditableStaticPageSlug } from '$lib/staticPageContent'

const STATIC_PAGE_REQUEST_TIMEOUT_MS = 2_500

export const loadEditableStaticPage = async (
  { fetch, url }: { fetch: typeof globalThis.fetch; url: URL },
  slug: EditableStaticPageSlug
) => {
  const language = languageFromPathname(url.pathname) ?? originalPostLanguage
  const requestUrl = new URL(buildStaticPageContentUrl(slug, { language }), url.origin)
  const fallback = getLocalizedDefaultStaticPage(slug, language)
  const response = await fetchWithTimeout(
    fetch,
    requestUrl,
    {
      cache: 'no-store',
    },
    STATIC_PAGE_REQUEST_TIMEOUT_MS
  )

  let pageContent = fallback.content
  let pageExists = false
  let pageTitle = fallback.title
  let isTranslated = false
  let languageVersions: BackendStaticPageLanguageVersion[] = []

  if (response?.ok) {
    const data = await response.json().catch(() => ({}))
    if (data?.page) {
      pageExists = !!data.page.exists
      isTranslated = !!data.page.is_translated
      languageVersions = Array.isArray(data.page.language_versions)
        ? data.page.language_versions
        : []
      if (pageExists) {
        pageTitle = data.page.title ?? fallback.title
        pageContent = data.page.content ?? ''
      }
    }
  }

  return {
    language,
    pageTitle,
    pageContent,
    pageExists,
    isTranslated,
    languageVersions,
  }
}
