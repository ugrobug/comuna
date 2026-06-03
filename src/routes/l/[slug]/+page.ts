import { error } from '@sveltejs/kit'
import { buildLandingPageUrl } from '$lib/api/backend'

export type LandingPageImage = {
  id: number
  slot: string
  title: string
  alt_text?: string
  image_url: string
  is_active: boolean
  sort_order: number
}

export type LandingPage = {
  id: number
  slug: string
  title: string
  description: string
  template_slug: string
  is_published: boolean
  url: string
  images: LandingPageImage[]
}

export async function load({ fetch, params }) {
  const response = await fetch(buildLandingPageUrl(params.slug), {
    cache: 'no-store',
    credentials: 'include',
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || !data?.page) {
    throw error(response.status || 404, data?.error || 'Landing page not found')
  }
  return {
    landingPage: data.page as LandingPage,
  }
}
