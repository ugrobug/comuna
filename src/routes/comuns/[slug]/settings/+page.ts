import { redirect } from '@sveltejs/kit'

export const load = async ({ params }) => {
  throw redirect(307, `/comuns/${encodeURIComponent(params.slug)}?settings=1`)
}
