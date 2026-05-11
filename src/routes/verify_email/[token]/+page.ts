import { verifyEmail } from '$lib/siteAuth'
import { error } from '@sveltejs/kit'

export async function load({ fetch, params }) {
  try {
    await verifyEmail(params.token, fetch)
  } catch (err) {
    throw error(400, (err as Error)?.message || 'Не удалось подтвердить почту')
  }
}
