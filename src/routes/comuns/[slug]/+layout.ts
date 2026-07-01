import ComunSidebarInfo from '$lib/components/ui/sidebar/ComunSidebarInfo.svelte'
import { buildComunSidebarUrl, buildComunUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, url, depends }) => {
  const slug = params.slug
  depends(`app:comun:${slug}`)

  const comunResponse = await fetch(new URL(buildComunUrl(slug), url.origin).toString())
  if (!comunResponse.ok) {
    if (comunResponse.status === 404) {
      throw error(404, 'site.errors.communityNotFound')
    }
    throw error(comunResponse.status, 'Не удалось загрузить сообщество')
  }

  const comunPayload = await comunResponse.json()
  let sidebarComun = comunPayload?.comun ?? null
  try {
    const sidebarResponse = await fetch(new URL(buildComunSidebarUrl(slug), url.origin).toString())
    if (sidebarResponse.ok) {
      const sidebarPayload = await sidebarResponse.json()
      sidebarComun = sidebarPayload?.comun ?? sidebarComun
    }
  } catch {
    sidebarComun = comunPayload?.comun ?? null
  }

  return {
    slug,
    comun: comunPayload?.comun ?? null,
    slots: comunPayload?.comun
      ? {
          sidebar: {
            component: ComunSidebarInfo,
            props: {
              comun: sidebarComun,
            },
          },
        }
      : undefined,
  }
}
