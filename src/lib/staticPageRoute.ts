import { buildStaticPageContentUrl, type BackendStaticPageLanguageVersion } from '$lib/api/backend'
import { languageFromPathname, originalPostLanguage } from '$lib/postLanguages'
import { getDefaultStaticPageContent, type EditableStaticPageSlug } from '$lib/staticPageContent'

export const loadEditableStaticPage = async (
  { fetch, url }: { fetch: typeof globalThis.fetch; url: URL },
  slug: EditableStaticPageSlug
) => {
  const language = languageFromPathname(url.pathname) ?? originalPostLanguage
  const requestUrl = new URL(buildStaticPageContentUrl(slug, { language }), url.origin)
  const response = await fetch(requestUrl.toString(), { cache: 'no-store' })

  let pageContent = getDefaultStaticPageContent(slug)
  let pageExists = false
  let pageTitle = ''
  let isTranslated = false
  let languageVersions: BackendStaticPageLanguageVersion[] = []

  if (response.ok) {
    const data = await response.json().catch(() => ({}))
    if (data?.page) {
      pageExists = !!data.page.exists
      pageTitle = data.page.title ?? ''
      isTranslated = !!data.page.is_translated
      languageVersions = Array.isArray(data.page.language_versions)
        ? data.page.language_versions
        : []
      if (pageExists) {
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
