import { redirect } from '@sveltejs/kit'
import type { PageLoad } from './$types'

export const load: PageLoad = () => {
  throw redirect(301, '/s/365-films/admin')
}
