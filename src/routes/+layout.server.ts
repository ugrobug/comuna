import { originalPostLanguage } from '$lib/postLanguages.js'

export const load = async ({ locals }) => {
  return {
    preferredLanguage: locals.preferredLanguage || originalPostLanguage,
    authBootstrap: locals.authBootstrap || null,
  }
}
