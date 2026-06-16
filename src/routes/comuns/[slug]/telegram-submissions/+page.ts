import { error } from '@sveltejs/kit'

export const load = async ({ parent, url }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null
  if (!comun?.slug) {
    throw error(404, 'Сообщество не найдено')
  }
  if (!comun?.can_moderate) {
    throw error(403, 'Недостаточно прав')
  }

  return {
    comun,
    status: url.searchParams.get('status') || 'pending',
    focusId: Number(url.searchParams.get('id') || 0) || null,
  }
}
