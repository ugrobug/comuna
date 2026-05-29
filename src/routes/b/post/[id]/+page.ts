import ComunSidebarInfo from '$lib/components/ui/sidebar/ComunSidebarInfo.svelte'
import { buildComunUrl, buildPostDetailUrl } from '$lib/api/backend'
import { slugifyTitle } from '$lib/util/slug'
import { error, redirect } from '@sveltejs/kit'

export const ssr = true

export const load = async ({ params, fetch, url }) => {
  const rawId = params.id
  const id = Number(rawId.split('-')[0])
  if (!Number.isInteger(id) || id <= 0) {
    throw error(404, 'Пост не найден')
  }

  const response = await fetch(buildPostDetailUrl(id))
  if (!response.ok) {
    let payload: { redirect_url?: string } = {}
    try {
      payload = await response.json()
    } catch {
      payload = {}
    }
    if (payload.redirect_url) {
      throw redirect(302, payload.redirect_url)
    }
    throw error(response.status, 'Пост не найден')
  }

  const data = await response.json()
  const comunSlug = data.post?.comun?.slug || data.post?.comun_slug || ''
  let sidebarComun = data.post?.comun ?? null

  if (comunSlug) {
    try {
      const comunResponse = await fetch(new URL(buildComunUrl(comunSlug), url.origin).toString())
      if (comunResponse.ok) {
        const comunPayload = await comunResponse.json()
        sidebarComun = comunPayload?.comun ?? sidebarComun
      }
    } catch {
      sidebarComun = data.post?.comun ?? null
    }
  }

  const slug = slugifyTitle(data.post?.title ?? '')
  const canonicalId = slug ? `${id}-${slug}` : `${id}`

  return {
    post: data.post,
    canonicalId,
    slots: sidebarComun
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
