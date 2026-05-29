import { redirect } from '@sveltejs/kit'
import type { PageLoad } from './$types'

export const load: PageLoad = ({ params }) => {
  throw redirect(301, `/s/365-films/admin/preview/${encodeURIComponent(params.filmId)}`)
}
