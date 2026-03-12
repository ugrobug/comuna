import { loadEditableStaticPage } from '$lib/staticPageRoute'

export const load = async ({ fetch, url }) => loadEditableStaticPage({ fetch, url }, 'rules')
