import { originalPostLanguage } from '$lib/postLanguages.js'

export const load = async ({ locals }) => {
  return {
    language: locals.language || originalPostLanguage,
    authBootstrap: locals.authBootstrap || null,
  }
}
