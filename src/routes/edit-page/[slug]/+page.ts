import { error } from '@sveltejs/kit'
import {
  EDITABLE_STATIC_PAGE_META,
  isEditableStaticPageSlug,
} from '$lib/staticPageContent'
import { loadEditableStaticPage } from '$lib/staticPageRoute'

export const load = async ({ fetch, params, url }) => {
  const slug = String(params.slug || '').trim().toLowerCase()

  if (!isEditableStaticPageSlug(slug)) {
    throw error(404, 'Page not found')
  }

  const pageData = await loadEditableStaticPage({ fetch, url }, slug)

  return {
    slug,
    ...EDITABLE_STATIC_PAGE_META[slug],
    ...pageData,
  }
}
