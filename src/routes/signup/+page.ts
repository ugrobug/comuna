import { DEFAULT_INSTANCE_URL } from '$lib/instance.js'
import { redirect } from '@sveltejs/kit'

export const load = () => {
  redirect(302, `/signup/${DEFAULT_INSTANCE_URL}`)
}
