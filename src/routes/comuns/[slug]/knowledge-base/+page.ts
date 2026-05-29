import { buildComunKnowledgeBaseUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, parent, url }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null
  if (!comun?.slug) {
    throw error(404, 'Сообщество не найдено')
  }

  if (!comun?.knowledge_base_enabled && !comun?.can_moderate) {
    throw error(404, 'База знаний не включена')
  }

  const response = await fetch(
    new URL(buildComunKnowledgeBaseUrl(comun.slug), url.origin).toString()
  )
  if (!response.ok) {
    throw error(response.status, 'Не удалось загрузить базу знаний')
  }

  const payload = await response.json().catch(() => ({}))
  return {
    comun: payload?.comun ?? comun,
    items: payload?.items ?? [],
    flatItems: payload?.flat_items ?? [],
  }
}
