import { redirect } from '@sveltejs/kit'

export const load = ({ url }) => {
  const next = url.searchParams.get('next')
  if (next) {
    throw redirect(302, `/settings?next=${encodeURIComponent(next)}`)
  }
  throw redirect(302, '/settings')
}
